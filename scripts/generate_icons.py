"""Rebuild bundled Crystal derivatives, ICO and contact sheet from preserved originals."""
import json
import struct
from pathlib import Path
from PySide2.QtCore import Qt, QRect, QByteArray, QBuffer, QIODevice
from PySide2.QtGui import QImage, QPainter, QColor, QFont, QColorSpace
from PySide2.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'src/edpd/assets'


def original(name, size):
    available = sorted(int(p.parent.name) for p in (ASSETS / 'original').glob(f'*/{name}.png'))
    chosen = min(available, key=lambda n: (n < size, abs(n-size)))
    image = QImage(str(ASSETS / 'original' / str(chosen) / (name+'.png')))
    assert not image.isNull(), name
    image.setColorSpace(QColorSpace())
    return image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_ARGB32)


def tint(image, hue, predicate=lambda c, y: True):
    image = image.copy()
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x,y)
            if c.alpha() and predicate(c, y):
                c.setHslF(hue, .60, c.lightnessF(), c.alphaF())
                image.setPixelColor(x,y,c)
    return image


def overlay(base, top, rect):
    result=base.copy(); p=QPainter(result); p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect,top);p.end();return result


def build():
    manifest=json.loads((ASSETS/'manifest.json').read_text())
    for size in (22,32,48,64,128,256):
        out=ASSETS/'icons'/str(size);out.mkdir(parents=True,exist_ok=True)
        for name in manifest['icons']:
            image=original(name,size)
            if name=='extract': image=tint(image,.13,lambda c,y: 15<=c.hue()<=65)
            if name in ('delete','settings'): image=tint(image,.60)
            if name=='refresh': image=tint(image,.58,lambda c,y: c.saturation()>70 and y<size//2)
            if name=='clear':
                image=tint(image,.13)
                for y in range(size):
                    for x in range(size):
                        c=image.pixelColor(x,y)
                        if c.alpha(): c.setHslF(.13,.85,c.lightnessF()*.85,c.alphaF());image.setPixelColor(x,y,c)
                image=overlay(image,tint(original('delete',size),.60),QRect(size//3,size//3,2*size//3,2*size//3))
            if name=='width':
                image=overlay(image,original('previous',size),QRect(0,2*size//3,size//3,size//3))
                image=overlay(image,original('next',size),QRect(2*size//3,2*size//3,size//3,size//3))
            assert image.save(str(out/(name+'.png')))
        # Actual Crystal envelope and PDF sheet, combined without a new icon family.
        app=overlay(original('mail',size),original('pdf',size),QRect(size//3,size//4,2*size//3,3*size//4))
        app.save(str(out/'app.png'))
    frames=[]
    for size in (16,24,32,48,64,128,256):
        image=QImage(str(ASSETS/'icons'/'256'/'app.png')).scaled(size,size,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');frames.append((size,bytes(data)))
    header=struct.pack('<HHH',0,1,len(frames));offset=6+16*len(frames);entries=b'';body=b''
    for size,data in frames:
        entries+=struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset)
        body+=data;offset+=len(data)
    (ASSETS/'edpd.ico').write_bytes(header+entries+body)
    labels={'extract':'Kicsomagolás','delete':'Kijelölt nap törlése','clear':'Munkamappa ürítése','refresh':'Frissítés','settings':'Beállítások','about':'Névjegy','first':'Első oldal','previous':'Előző oldal','next':'Következő oldal','last':'Utolsó oldal','zoom_in':'Nagyítás','zoom_out':'Kicsinyítés','width':'Szélesség','page':'Teljes oldal','print':'Nyomtatás','zip':'ZIP-csomag','pdf':'PDF-dokumentum','warning':'Hiba / figyelmeztetés','app':'EDPD alkalmazásikon'}
    sheet=QImage(1000,((len(labels)+3)//4)*145,QImage.Format_ARGB32);sheet.fill(Qt.white)
    painter=QPainter(sheet);painter.setFont(QFont('DejaVu Sans',11))
    for i,(name,label) in enumerate(labels.items()):
        x=(i%4)*250;y=(i//4)*145
        path=ASSETS/'icons'/('128' if name=='app' else '32' if name in ('extract','delete','clear','refresh','settings','about') else '22')/(name+'.png')
        painter.drawImage(QRect(x+93,y+10,64,64),QImage(str(path)))
        painter.drawText(QRect(x+5,y+85,240,50),Qt.AlignCenter|Qt.TextWordWrap,label)
    painter.end();sheet.save(str(ROOT/'docs/icon-comparison.png'))


if __name__=='__main__':
    app=QApplication([]);build()
