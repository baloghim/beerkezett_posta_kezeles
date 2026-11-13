"""Render preserved upstream SVG/PNG files with Qt 5.15, without redrawing icons."""
import json
from pathlib import Path
from PySide2.QtCore import Qt, QRectF
from PySide2.QtGui import QImage, QPainter, QFont
from PySide2.QtSvg import QSvgRenderer
from PySide2.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'src/edpd/assets'


def build():
    manifest = json.loads((ASSETS / 'themes.json').read_text())
    for theme, record in manifest['themes'].items():
        if theme == 'Crystal SVG':
            continue
        directory = ASSETS / 'themes' / record['id']
        for role, item in record['icons'].items():
            source = directory / 'original' / item['original']
            for size in (22,40):
                output = directory / str(size) / (role + '.png')
                output.parent.mkdir(parents=True, exist_ok=True)
                if source.suffix == '.svg':
                    renderer = QSvgRenderer(str(source))
                    assert renderer.isValid(), source
                    image = QImage(size,size,QImage.Format_ARGB32)
                    image.fill(Qt.transparent)
                    painter = QPainter(image)
                    renderer.render(painter, QRectF(0,0,size,size))
                    painter.end()
                else:
                    image = QImage(str(source)).scaled(size,size,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                assert not image.isNull() and image.save(str(output)), source
    from edpd.ui.icons import IconThemeManager
    themes = IconThemeManager()
    labels = {'extract':'Kicsomagolás','delete':'Kijelölt nap törlése','clear':'Munkamappa ürítése',
              'refresh':'Frissítés','settings':'Beállítások','about':'Névjegy','first':'Első oldal',
              'previous':'Előző oldal','next':'Következő oldal','last':'Utolsó oldal','zoom_in':'Nagyítás',
              'zoom_out':'Kicsinyítés','width':'Szélesség','page':'Teljes oldal','print':'Nyomtatás',
              'save':'PDF mentése','zip':'ZIP','pdf':'PDF','warning':'Figyelmeztetés'}
    image = QImage(1180,80+len(labels)*66,QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    painter.setFont(QFont('DejaVu Sans',10))
    for column, name in enumerate(manifest['themes']):
        themes.set_theme(name)
        x = 230 + column*190
        painter.drawText(x,12,185,50,Qt.AlignCenter|Qt.TextWordWrap,name)
        for row,(role,label) in enumerate(labels.items()):
            y = 80 + row*66
            if column == 0:
                painter.drawText(8,y,210,48,Qt.AlignVCenter,label)
            painter.drawPixmap(x+72,y+5,themes.icon(role).pixmap(40,40))
            if themes.sources[role] != name:
                painter.drawText(x,y+45,185,18,Qt.AlignCenter,'Crystal fallback')
    painter.end()
    image.save(str(ROOT/'docs/icon-theme-comparison.png'))


if __name__ == '__main__':
    app = QApplication([])
    build()
