"""Original vector gradients. No textures, external fonts, animations or OS calls."""
from functools import lru_cache
from .palettes import PALETTES
from ...surface_styles import LUNA


def gradient(top, middle, bottom):
    return f'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:0.48 {middle},stop:1 {bottom})'


@lru_cache(maxsize=len(PALETTES))
def stylesheet(name):
    c = PALETTES[name]
    if name == LUNA:
        return luna_stylesheet(c)
    glass = gradient(c['top'], c['middle'], c['bottom'])
    title = (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {c['title_top']},"
             f"stop:0.17 {c['title_mid']},stop:0.20 {c['title_bottom']},stop:1 {c['title_mid']})")
    hover = gradient(c['hover_top'], c['middle'], c['hover_bottom'])
    return f'''
QMainWindow#edpd-window, QDialog, QMessageBox {{ background: {c['window']}; }}
QToolBar#main-toolbar, QToolBar#pdf-toolbar {{
    background: {glass}; border: 1px solid {c['edge']}; border-top-color: {c['shine']};
    border-radius: 5px; padding: 1px 2px;
}}
QToolBar#operation-toolbar, QWidget#toolbar-controls {{ background: transparent; border: none; padding: 0; }}
QToolBar#pdf-toolbar QToolButton {{ padding: 2px 1px; }}
QToolBar#operation-toolbar QToolButton {{ border-right-color: {c['bottom']}; }}
QToolBar::separator {{ background: {c['edge']}; width: 1px; margin: 4px 6px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 3px; padding: 2px 4px; }}
QToolButton:hover {{ background: {hover}; border-color: {c['edge']}; border-top-color: {c['shine']}; }}
QToolButton:pressed, QToolButton:checked {{
    background: {gradient(c['pressed'], c['hover_bottom'], c['middle'])};
    border: 1px solid {c['title_edge']}; border-bottom-color: {c['shine']};
}}
QToolButton:disabled {{ color: {c['disabled']}; background: transparent; }}
QPushButton {{ background: {glass}; border: 1px solid {c['edge']}; border-top-color: {c['shine']};
    border-radius: 4px; padding: 4px 10px; min-height: 18px; }}
QPushButton:hover {{ background: {hover}; border-color: {c['selection_edge']}; }}
QPushButton:pressed {{ background: {c['pressed']}; border-top-color: {c['title_edge']}; }}
QPushButton:default, QPushButton:focus {{ border: 2px solid {c['selection_edge']}; padding: 3px 9px; }}
QPushButton:disabled {{ color: {c['disabled']}; background: {c['window']}; }}
QWidget#edpd-panel {{ background: {c['field']}; border: 1px solid {c['edge']}; border-radius: 5px; }}
QLabel#panel-title {{ background: {title}; color: {c['title_text']}; font-weight: bold;
    border: 1px solid {c['title_edge']}; border-top-color: {c['shine']};
    border-top-left-radius: 4px; border-top-right-radius: 4px; padding: 4px 8px; }}
QTableView {{ background: {c['field']}; alternate-background-color: {c['alternate']};
    gridline-color: {c['middle']}; border: 1px solid {c['edge']}; border-radius: 3px; }}
QTableView::item {{ padding: 2px; }}
QTableView::item:selected {{ border-top: 1px solid {c['selection_edge']}; border-bottom: 1px solid {c['selection_edge']}; }}
QHeaderView::section {{ background: {glass}; color: {c['text']}; font-weight: bold;
    padding: 4px 5px; border: none; border-right: 1px solid {c['edge']}; border-bottom: 1px solid {c['edge']}; }}
QTableCornerButton::section {{ background: {glass}; border: 1px solid {c['edge']}; }}
QScrollArea#pdf-scroll {{ background: {c['viewport']}; border: 1px solid {c['edge']}; border-radius: 3px; }}
QWidget#pdf-viewport {{ background: {c['viewport']}; }}
QLabel#pdf-page {{ background: white; color: {c['text']}; }}
QStatusBar#edpd-status {{ background: {glass}; border-top: 1px solid {c['shine']}; color: {c['text']}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {c['window']}; }}
QSplitter::handle:hover {{ background: {c['bottom']}; }}
QLineEdit, QComboBox, QTextBrowser {{ background: {c['field']}; color: {c['text']};
    border: 1px solid {c['edge']}; border-radius: 3px; padding: 3px; }}
QLineEdit:focus, QComboBox:focus, QTextBrowser:focus {{ border-color: {c['selection_edge']}; }}
QComboBox::drop-down {{ border-left: 1px solid {c['edge']}; width: 18px; background: {glass}; }}
QComboBox QAbstractItemView {{ background: {c['field']}; }}
QGroupBox {{ border: 1px solid {c['edge']}; border-radius: 4px; margin-top: 10px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {c['text']}; }}
QProgressBar {{ border: 1px solid {c['edge']}; border-radius: 3px; background: {c['field']}; text-align: center; }}
QProgressBar::chunk {{ background: {gradient(c['title_top'],c['title_mid'],c['title_bottom'])}; border-radius: 2px; }}
QMenu {{ background: {c['top']}; color: {c['text']}; border: 1px solid {c['edge']}; }}
QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
QToolTip {{ background: {c['top']}; color: {c['text']}; border: 1px solid {c['edge']}; padding: 4px; }}
'''


def luna_stylesheet(c):
    """Original XP-inspired chrome: cream toolbars, royal-blue panels, warm rims.

    Separate rules deliberately keep Longhorn's glass bands and geometry intact.
    No Microsoft bitmap, msstyles, DLL, font or external theme engine is used.
    """
    cream = gradient(c['top'], c['middle'], c['bottom'])
    button = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.56 #f7f5ee,stop:1 #dedbc8)'
    panel = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #69a4ff,stop:0.10 #367cf3,stop:0.46 #1259e4,stop:1 #003bb4)'
    warm = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fffdf4,stop:0.55 #fff0c5,stop:1 #ffd27d)'
    inset = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #bdcce5,stop:0.45 #e0e8f5,stop:1 #f2f5fb)'
    return f'''
QMainWindow#edpd-window {{ background: #e4eaf5; }}
QDialog, QMessageBox {{ background: {c['window']}; }}
QToolBar#main-toolbar, QToolBar#pdf-toolbar {{
    background: {cream}; border: 1px solid #aca899; border-top-color: white;
    border-bottom: 2px solid #c5c2b2; border-radius: 2px; padding: 1px 2px;
}}
QToolBar#operation-toolbar, QWidget#toolbar-controls {{ background: transparent; border: none; padding: 0; }}
QToolBar#pdf-toolbar QToolButton {{ padding: 2px 1px; }}
QToolBar#operation-toolbar QToolButton {{ border-right-color: #d2cfbd; }}
QToolBar::separator {{ background: #c5c2b2; width: 1px; margin: 4px 6px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 3px; padding: 2px 4px; color: {c['text']}; }}
QToolButton:hover {{ background: {warm}; border: 1px solid #e59700; }}
QToolButton:pressed, QToolButton:checked {{ background: {inset};
    border: 1px solid #315d9d; border-top-color: #244571; border-bottom-color: white; }}
QToolButton:focus {{ border-color: #e59700; }}
QToolButton:disabled {{ color: {c['disabled']}; background: transparent; border-color: transparent; }}
QPushButton {{ background: {button}; border: 1px solid #003c74;
    border-top-color: #6288b3; border-bottom-color: #003061; border-radius: 4px;
    padding: 4px 10px; min-height: 18px; color: {c['text']}; }}
QPushButton:hover {{ background: {warm}; border-color: #df9a21; }}
QPushButton:pressed {{ background: {inset}; border-top-color: #20466b; border-bottom-color: white; }}
QPushButton:default, QPushButton:focus {{ border: 2px solid #e3a13a; padding: 3px 9px; }}
QPushButton:disabled {{ background: #eeecdf; border-color: #b2b0a6; color: {c['disabled']}; }}
QWidget#edpd-panel {{ background: {c['field']}; border: 1px solid #6c9be5; border-radius: 4px; }}
QLabel#panel-title {{ background: {panel}; color: white; font-weight: bold;
    border: 1px solid #003caa; border-top-color: #a6caff;
    border-top-left-radius: 4px; border-top-right-radius: 4px; padding: 4px 8px; }}
QTableView {{ background: white; alternate-background-color: {c['alternate']};
    gridline-color: #e1e7f2; border: 1px solid #7f9db9; border-radius: 0px; }}
QTableView::item {{ padding: 2px; }}
QTableView::item:selected {{ border-top: 1px solid #003c74; border-bottom: 1px solid #003c74; }}
QHeaderView::section {{ background: {cream}; color: #111111; font-weight: bold;
    padding: 4px 5px; border: none; border-top: 1px solid white;
    border-right: 1px solid #c5c2b2; border-bottom: 1px solid #aca899; }}
QHeaderView::section:hover {{ background: {warm}; border-bottom-color: #e59700; }}
QTableCornerButton::section {{ background: {cream}; border: 1px solid #aca899; }}
QScrollArea#pdf-scroll {{ background: {c['viewport']}; border: 1px solid #7f9db9; border-radius: 0px; }}
QWidget#pdf-viewport {{ background: {c['viewport']}; }}
QLabel#pdf-page {{ background: white; color: #111111; }}
QStatusBar#edpd-status {{ background: {cream}; border-top: 1px solid white;
    border-bottom: 1px solid #aca899; color: #111111; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: #ece9d8; border-left: 1px solid white; }}
QSplitter::handle:hover {{ background: #d2e3ff; }}
QLineEdit, QComboBox, QTextBrowser {{ background: white; color: #111111;
    border: 1px solid #7f9db9; border-radius: 2px; padding: 3px; }}
QLineEdit:focus, QComboBox:focus, QTextBrowser:focus {{ border: 2px solid #e3a13a; padding: 2px; }}
QLineEdit:disabled, QComboBox:disabled {{ background: #efede3; color: {c['disabled']}; }}
QComboBox::drop-down {{ border-left: 1px solid #7f9db9; width: 18px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e1edff,stop:1 #a5c4f1); }}
QComboBox::drop-down:hover {{ background: {warm}; }}
QComboBox QAbstractItemView {{ background: white; color: #111111; }}
QGroupBox {{ border: 1px solid #b0b6c3; border-radius: 4px; margin-top: 10px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #003caa; }}
QProgressBar {{ border: 1px solid #7f9db9; border-radius: 2px; background: white;
    color: #111111; text-align: center; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #b6ef89,stop:0.4 #6bc941,stop:1 #39a528);
    border: 1px solid #479d2d; border-radius: 0px; width: 9px; margin: 1px; }}
QSlider::groove:horizontal {{ height: 4px; border: 1px solid #9d9c91; background: #f7f6ee; }}
QSlider::handle:horizontal {{ width: 11px; margin: -6px 0; border: 1px solid #4f78ad;
    border-radius: 2px; background: {button}; }}
QSlider::handle:horizontal:hover {{ background: {warm}; border-color: #e59700; }}
QMenu {{ background: #fffef8; color: #111111; border: 1px solid #7f9db9; }}
QMenu::item:selected {{ background: {c['selection']}; color: white; }}
QMenu::item:disabled {{ color: {c['disabled']}; }}
QToolTip {{ background: #ffffe1; color: #111111; border: 1px solid #767676; padding: 4px; }}
'''
