"""Original vector gradients. No textures, external fonts, animations or OS calls."""
from functools import lru_cache
from .palettes import PALETTES


def gradient(top, middle, bottom):
    return f'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:0.48 {middle},stop:1 {bottom})'


@lru_cache(maxsize=2)
def stylesheet(name):
    c = PALETTES[name]
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
