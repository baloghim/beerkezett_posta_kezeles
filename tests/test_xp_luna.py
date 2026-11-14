"""Luna visual/contrast regressions, including the unchanged Longhorn output."""
import hashlib
import pytest
from PySide2.QtCore import Qt, QEvent, QPointF
from PySide2.QtGui import QColor, QPalette, QHoverEvent
from PySide2.QtWidgets import QStyleOptionViewItem
from edpd.config import Settings
from edpd.surface_styles import CUSTOM_SURFACES, LUNA
from edpd.ui.appearance import apply_style, current_style_name
from edpd.ui.main_window import MainWindow, row_appearance
from edpd.ui.themes import set_theme, manager
from edpd.ui.themes.palettes import PALETTES
from edpd.ui.themes.styles import stylesheet
from edpd.ui.themes.widgets import selected_text_colour


@pytest.fixture(autouse=True)
def restore_surface(app):
    previous_style=current_style_name()
    previous_surface=manager().name
    yield
    apply_style(previous_style,previous_surface)


def luminance(colour):
    values=[channel/255 for channel in (colour.red(),colour.green(),colour.blue())]
    values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))


def test_longhorn_stylesheet_bytes_are_unchanged_and_cache_handles_all_surfaces():
    expected={'Longhorn Blue':'1d6ee319949a7c6eac82b56b8c96ad0a3458e60094f89051124dd9e9c592de5e',
              'Longhorn Slate':'307c6cbfa7fef72230668ddd8d7718d29e638f89ad3410dda640c1a6d40bb071'}
    before={name:stylesheet(name) for name in CUSTOM_SURFACES}
    for _ in range(5):
        for name in reversed(CUSTOM_SURFACES):assert stylesheet(name)==before[name]
    for name,digest in expected.items():
        assert hashlib.sha256(stylesheet(name).encode()).hexdigest()==digest
    assert stylesheet.cache_info().maxsize>=len(CUSTOM_SURFACES)
    assert stylesheet(LUNA)!=stylesheet('Longhorn Blue')


def test_luna_selected_state_text_has_readable_contrast(app,folders):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target),ui_style=LUNA),auto_refresh=False)
    table=window.day_table
    states=('Feldolgozva','Részben kicsomagolva','Hibás csomag','Kicsomagolva')
    table.setRowCount(len(states))
    try:
        for row,state in enumerate(states):
            expected=QColor(row_appearance(state)[0])
            window.fill(table,row,['2026.11.14.','synthetic.zip','2',state],appearance=row_appearance(state))
            option=QStyleOptionViewItem()
            table.itemDelegate().initStyleOption(option,table.model().index(row,3))
            text=option.palette.color(QPalette.HighlightedText)
            assert text==selected_text_colour(expected,LUNA)
            background=QColor(PALETTES[LUNA]['selection'])
            a,b=sorted((luminance(text),luminance(background)))
            assert (b+.05)/(a+.05)>=4.5
            assert table.item(row,3).foreground().color()==expected
    finally:
        window.close();set_theme('Alapértelmezett')


def test_luna_toolbar_button_hover_pressed_and_disabled_paint_distinctly(app,folders):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target),ui_style=LUNA),auto_refresh=False)
    window.show();app.processEvents()
    button=window.operation_toolbar.widgetForAction(window.actions[-1])
    try:
        # Route the same Qt hover events without relying on a headless OS cursor.
        button.setAttribute(Qt.WA_UnderMouse,False)
        app.sendEvent(button,QHoverEvent(QEvent.HoverLeave,QPointF(-1,-1),QPointF(1,1)))
        button.update();app.processEvents()
        normal=button.grab().toImage()
        button.setAttribute(Qt.WA_UnderMouse,True)
        app.sendEvent(button,QHoverEvent(QEvent.HoverEnter,QPointF(1,1),QPointF(-1,-1)))
        button.update();app.processEvents()
        hover=button.grab().toImage()
        button.setDown(True);app.processEvents()
        pressed=button.grab().toImage()
        button.setDown(False);button.setEnabled(False);app.processEvents()
        disabled=button.grab().toImage()
        assert normal!=hover and hover!=pressed and pressed!=disabled
    finally:
        button.setEnabled(True);window.close();set_theme('Alapértelmezett')
