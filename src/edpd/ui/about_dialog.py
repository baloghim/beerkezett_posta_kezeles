from PySide2.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextBrowser, QDialogButtonBox
from .. import __version__, DISPLAY_NAME
from .icons import icon


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        display_name = getattr(parent, 'display_name', DISPLAY_NAME)
        self.setWindowTitle(f'{display_name} – Névjegy')
        self.resize(640, 540)
        self.setWindowIcon(icon('app'))
        layout = QVBoxLayout(self)
        self.app_icon = QLabel()
        self.app_icon.setPixmap(icon('app').pixmap(64, 64))
        layout.addWidget(self.app_icon)
        self.info = QTextBrowser()
        description = ('Napi ZIP-csomagok és PDF-dokumentumok közvetlen böngészése, nyomtatása és egyenkénti mentése. '
                       'A Betekintő nem használ munkamappát.' if display_name == 'EDPD Betekintő' else
                       'A Magyar Posta EDPD szolgáltatásán keresztül érkező, digitalizált postai '
                       'dokumentumok napi ZIP-csomagjainak kezelése, kicsomagolása, megtekintése és nyomtatása.')
        self.info.setHtml(
            f'<h2>{display_name}</h2><p>Verzió: {__version__}</p>'
            f'<p>{description}</p>'
            '<p>Helyben futó, telemetria nélküli alkalmazás.<br>'
            '<a href="https://github.com/baloghim/beerkezett_posta_kezeles">GitHub projekt</a></p>'
            '<p>Technológiák: Python 3.10, PySide2 / Qt 5.15, PyMuPDF / MuPDF.</p>'
            '<p>A projekt saját kódjára a jogtulajdonos még nem választott terjesztési licencet.</p>'
            '<p>PySide2 / Qt: LGPLv3, GPLv3 vagy kereskedelmi licenc, '
            'a komponens feltételei szerint.<br>PyMuPDF / MuPDF: GNU AGPLv3 vagy Artifex kereskedelmi licenc.'
            '<br>PyInstaller: GPLv2, a terjesztett alkalmazásra vonatkozó kivétellel.</p>'
            '<p>Crystal Remix ikonok: Everaldo Coelho; modern átdolgozás: Viet Dang (Đặng Việt Dũng). '
            f'GNU LGPL (az upstream nem jelöl verziót). Az {display_name} színezett és kombinált változatokat is használ. '
            'A források és licencszövegek a csomag assets és licenses mappáiban találhatók.</p>'
            '<p>Választható belső ikonok:<br>Crystal SVG: Everaldo Coelho, Viet Dang; GNU LGPL (verziójelölés nélkül).<br>'
            'Nuvola: David Vignoni; LGPL-2.1-or-later.<br>'
            'KDE Modern Classic: Shaun Belcher, eredeti KDE Classic művészek; LGPL-3.0-or-later, '
            'az örökölt elemekhez a LICENSE-KDE-Classic.txt is tartozik. Az upstream AI-segített rekonstrukcióként ismerteti.<br>'
            'Papirus: Papirus Development Team; GPL-3.0.<br>'
            'We10X: yeyushengfan258, Ubuntu Yaru közreműködők; GPL-3.0.<br>'
            'Részletes eredet és módosítások: assets/themes.json; teljes licencszövegek: licenses/.</p>')
        self.info.setOpenExternalLinks(True)
        layout.addWidget(self.info)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('Bezárás')
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
