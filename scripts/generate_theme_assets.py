"""Render preserved upstream SVG/PNG files with Qt 5.15, without redrawing icons."""
import json
import subprocess
import tempfile
from pathlib import Path
from PySide2.QtCore import Qt, QRectF
from PySide2.QtGui import QImage, QPainter, QFont
from PySide2.QtSvg import QSvgRenderer
from PySide2.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'src/edpd/assets'


def build():
    manifest = json.loads((ASSETS / 'themes.json').read_text())
    def render(source, size, inkscape=False):
        if inkscape and source.suffix == '.svg':
            with tempfile.TemporaryDirectory(prefix='edpd-render-') as temp:
                output = Path(temp) / 'icon.png'
                subprocess.run(['inkscape', str(source), '--export-type=png',
                                '--export-width='+str(size), '--export-height='+str(size),
                                '--export-filename='+str(output)], check=True, capture_output=True)
                image = QImage(str(output)).copy()
        elif source.suffix == '.svg':
            renderer = QSvgRenderer(str(source))
            assert renderer.isValid(), source
            image = QImage(size, size, QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
        else:
            image = QImage(str(source)).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        assert not image.isNull(), source
        return image

    for theme, record in manifest['themes'].items():
        if theme == 'Crystal SVG':
            continue
        directory = ASSETS / 'themes' / record['id']
        for role, item in record['icons'].items():
            source = directory / 'original' / item['original']
            for size in (22, 40):
                output = directory / str(size) / (role + '.png')
                output.parent.mkdir(parents=True, exist_ok=True)
                image = render(source, size, 'renderer' in item)
                if 'badge' in item:
                    badge = render(directory / 'original' / item['badge']['original'], size//2, 'renderer' in item)
                    painter = QPainter(image)
                    painter.drawImage(size-size//2, size-size//2, badge)
                    painter.end()
                assert image.save(str(output)), output
    from edpd.ui.icons import IconThemeManager
    themes = IconThemeManager()
    labels = {'extract':'Kicsomagolás','delete':'Kijelölt nap törlése','clear':'Munkamappa ürítése',
              'refresh':'Frissítés','settings':'Beállítások','about':'Névjegy','first':'Első oldal',
              'previous':'Előző oldal','next':'Következő oldal','last':'Utolsó oldal','zoom_in':'Nagyítás',
              'zoom_out':'Kicsinyítés','width':'Szélesség','page':'Teljes oldal','print':'Nyomtatás',
              'save':'PDF mentése','zip':'ZIP','pdf':'PDF','warning':'Figyelmeztetés'}
    image = QImage(230+len(manifest['themes'])*170,80+len(labels)*66,QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    painter.setFont(QFont('DejaVu Sans',10))
    for column, name in enumerate(manifest['themes']):
        themes.set_theme(name)
        x = 230 + column*170
        painter.drawText(x,12,165,50,Qt.AlignCenter|Qt.TextWordWrap,name)
        for row,(role,label) in enumerate(labels.items()):
            y = 80 + row*66
            if column == 0:
                painter.drawText(8,y,210,48,Qt.AlignVCenter,label)
            painter.drawPixmap(x+62,y+5,themes.icon(role).pixmap(40,40))
            if themes.sources[role] != name:
                painter.drawText(x,y+45,165,18,Qt.AlignCenter,'Crystal fallback')
    painter.end()
    image.save(str(ROOT/'docs/icon-theme-comparison.png'))
    # The toolbar sheet uses the exact 40 px production PNGs, without enlargement.
    image = QImage(960, 72+len(manifest['themes'])*82, QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    painter.setFont(QFont('DejaVu Sans', 10))
    for column, (role, label) in enumerate(list(labels.items())[:6]):
        painter.drawText(205+column*125, 8, 122, 52, Qt.AlignCenter|Qt.TextWordWrap, label)
    for row, name in enumerate(manifest['themes']):
        themes.set_theme(name)
        y = 72+row*82
        painter.drawText(8, y, 195, 52, Qt.AlignVCenter|Qt.TextWordWrap, name)
        for column, role in enumerate(list(labels)[:6]):
            painter.drawPixmap(246+column*125, y+5, themes.icon(role).pixmap(40,40))
            if themes.sources[role] != name:
                painter.drawText(205+column*125,y+48,122,22,Qt.AlignCenter,'Crystal fallback')
    painter.end()
    assert image.save(str(ROOT/'docs/icon-toolbar-comparison.png'))



if __name__ == '__main__':
    app = QApplication([])
    build()
