import gc
import hashlib
import json
import time
import tracemalloc
import weakref
import pytest
from PySide2.QtCore import Qt, QCoreApplication, QEvent, QObject
from PySide2.QtGui import QPalette, QImage
from PySide2.QtWidgets import QApplication, QStyleFactory, QWidget
from edpd.config import Settings
from edpd.ui.appearance import apply_style, current_style_name
from edpd.ui.themes import manager, set_theme, THEME_NAMES
from edpd.ui.icons import set_theme as set_icons, icon, THEME_NAMES as ICON_NAMES
from edpd.ui.main_window import MainWindow, row_appearance
from edpd.ui.settings_dialog import SettingsDialog
from test_ui import wait_for


@pytest.fixture(autouse=True)
def restore_surface(app):
    original=current_style_name()
    set_theme('Alapértelmezett')
    set_icons('Crystal SVG')
    yield
    set_theme('Alapértelmezett')
    apply_style(original)
    set_icons('Crystal SVG')
    app.processEvents()


def test_choices_cancel_and_old_configuration(app,tmp_path):
    settings=Settings()
    assert settings.surface_theme=='Alapértelmezett'
    path=tmp_path/'settings.json'
    path.write_text('{"source":"archive","target":"workspace"}')
    assert Settings.load(path).surface_theme=='Alapértelmezett'
    path.write_text('{"source":"archive","target":"workspace","surface_theme":43}')
    assert Settings.load(path).source=='archive'
    assert Settings.load(path).surface_theme=='Alapértelmezett'
    settings.save(path)
    before=path.read_bytes()
    dialog=SettingsDialog(settings,None)
    assert tuple(dialog.surface_combo.itemText(i) for i in range(dialog.surface_combo.count()))==THEME_NAMES
    assert dialog.surface_combo.currentText()=='Alapértelmezett'
    dialog.surface_combo.setCurrentText('Longhorn Blue')
    dialog.reject()
    assert path.read_bytes()==before and settings.surface_theme=='Alapértelmezett'
    assert manager().name=='Alapértelmezett'


def test_saved_change_is_immediate_without_network_or_document_reload(app,folders,monkeypatch):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.show()
    app.processEvents()
    generation=window.source_generation
    import edpd.ui.main_window as module
    monkeypatch.setattr(module,'check_settings',lambda *_:pytest.fail('Surface switch accessed network'))
    def choose(dialog):
        dialog.surface_combo.setCurrentText('Longhorn Blue')
        return dialog.Accepted
    monkeypatch.setattr(SettingsDialog,'exec_',choose)
    try:
        window.configure()
        wait_for(app,lambda:not window.jobs)
        assert manager().name=='Longhorn Blue' and 'qlineargradient' in app.styleSheet()
        assert Settings.load().surface_theme=='Longhorn Blue'
        assert window.viewer.theme_title.isVisible()
        assert window.source_generation==generation
        dialog=SettingsDialog(window.settings,window)
        assert dialog.style_combo.currentData().lower()==current_style_name().lower()
        assert dialog.surface_combo.currentText()=='Longhorn Blue'
        dialog.reject()
        set_theme('Alapértelmezett')
        assert app.styleSheet()=='' and not window.viewer.theme_title.isVisible()
    finally:
        window.close()


@pytest.mark.parametrize('surface',THEME_NAMES[1:])
def test_all_native_styles_and_icon_themes_keep_pdf_pixels_and_state(app,folders,pdf_bytes,surface):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.show()
    viewer=window.viewer
    viewer.open_data(pdf_bytes)
    viewer.move(1)
    viewer.zoom(1.0/viewer.scale)
    app.processEvents()
    image=viewer.label.pixmap().toImage()
    document=viewer.pdf
    fixed_icon=icon('app').cacheKey()
    document.render=lambda *args:pytest.fail('Surface/icon change re-rendered a fixed-scale PDF')
    try:
        for style in QStyleFactory.keys():
            for icons in ICON_NAMES:
                apply_style(style,surface)
                set_icons(icons)
                app.processEvents()
                assert current_style_name().lower()==style.lower()
                assert manager().name==surface
                assert window.actions[0].icon().cacheKey()==icon('extract').cacheKey()
                assert viewer.print_action.icon().cacheKey()==icon('print').cacheKey()
                assert icon('app').cacheKey()==fixed_icon
                assert viewer.label.pixmap().toImage()==image
                assert viewer.pdf is document and viewer.pdf.data==pdf_bytes
                assert viewer.page==1 and viewer.fit_mode is None and abs(viewer.scale-1)<1e-8
                assert window.main_toolbar.iconSize().width()==40
                assert viewer.toolbar.iconSize().width()==22
    finally:
        viewer.pdf.close()
        window.close()


@pytest.mark.parametrize('surface',THEME_NAMES[1:])
def test_selected_status_colours_are_actually_painted(app,folders,surface):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.resize(1600,900)
    table=window.day_table
    table.setRowCount(3)
    states=('Feldolgozva','Részben kicsomagolva','Hibás csomag')
    for row,state in enumerate(states):
        window.fill(table,row,['2026.11.14.','synthetic.zip','2',state],appearance=row_appearance(state))
    set_theme(surface)
    window.show()
    app.processEvents()
    try:
        for row,state in enumerate(states):
            item=table.item(row,3)
            expected=row_appearance(state)[0]
            table.setCurrentCell(row,3)
            app.processEvents()
            assert item.foreground().color().name()==expected
            rect=table.visualItemRect(item)
            capture=table.viewport().grab(rect).toImage()
            coloured=0
            for y in range(capture.height()):
                for x in range(capture.width()):
                    c=capture.pixelColor(x,y)
                    if row==0: good=c.green()>c.red()*1.4 and c.green()>c.blue()*1.2
                    elif row==1: good=c.red()>c.green()*1.25 and c.green()>c.blue()*1.7
                    else: good=c.red()>c.green()*1.5 and c.red()>c.blue()*1.5
                    coloured+=bool(good)
            assert coloured>3,(surface,state,coloured)
    finally:
        window.close()


def test_repeated_restore_is_exact_and_does_not_accumulate_objects(app,folders):
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.show()
    apply_style('Fusion','Alapértelmezett')
    app.processEvents()
    palette=QPalette(app.palette())
    font=window.operation_toolbar.font().pointSizeF()
    native_widgets=[window,window.docs_table,window.day_table.horizontalHeader(),
                    window.viewer.scroll.viewport(),window.viewer.label,window.operation_toolbar]
    widget_palettes=[QPalette(widget.palette()) for widget in native_widgets]
    for theme in THEME_NAMES:
        set_theme(theme)
    app.processEvents()
    baseline=len(app.allWidgets())
    tracemalloc.start()
    gc.collect()
    before=tracemalloc.get_traced_memory()[0]
    try:
        for _ in range(25):
            for theme in THEME_NAMES:
                set_theme(theme)
                app.processEvents()
        gc.collect()
        growth=tracemalloc.get_traced_memory()[0]-before
        assert growth<180_000,growth
        assert len(app.allWidgets())<=baseline+1
        assert manager().name=='Longhorn Slate'
        set_theme('Alapértelmezett')
        app.processEvents()
        assert app.styleSheet()=='' and app.palette()==palette
        assert all(widget.styleSheet()=='' for widget in window.findChildren(QWidget))
        assert window.operation_toolbar.font().pointSizeF()==font
        assert not window.viewer.theme_title.isVisible()
        assert [widget.palette() for widget in native_widgets]==widget_palettes
    finally:
        tracemalloc.stop()
        window.close()


def test_missing_or_bad_theme_falls_back_without_losing_profile(app,monkeypatch):
    from edpd.ui.themes.palettes import PALETTES
    from edpd.ui.themes.styles import stylesheet
    base=QPalette(app.palette())
    set_theme('Longhorn Blue')
    assert set_theme('Missing theme')=='Alapértelmezett'
    assert app.styleSheet()=='' and app.palette()==base
    monkeypatch.delitem(PALETTES['Longhorn Blue'],'text')
    assert set_theme('Longhorn Blue')=='Alapértelmezett'
    monkeypatch.delitem(PALETTES,'Longhorn Slate')
    assert set_theme('Longhorn Slate')=='Alapértelmezett'


def test_destroyed_viewer_is_not_kept_alive_by_surface_subscription(app):
    from edpd.ui.pdf_viewer import PDFViewer
    widget=PDFViewer()
    reference=weakref.ref(widget)
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    del widget
    gc.collect()
    assert reference() is None
    set_theme('Longhorn Blue')


@pytest.mark.parametrize('surface',THEME_NAMES[1:])
def test_theme_at_initial_construction_keeps_larger_action_fonts(app,folders,surface):
    source,target=folders
    apply_style('Fusion',surface)
    window=MainWindow(Settings(source=str(source),target=str(target),surface_theme=surface),auto_refresh=False)
    window.show();app.processEvents()
    try:
        expected=app.font().pointSizeF()+2
        for style in QStyleFactory.keys():
            apply_style(style,surface);app.processEvents()
            assert all(window.operation_toolbar.widgetForAction(action).font().pointSizeF()==expected
                       for action in window.actions)
    finally:window.close()


def test_coloured_pdf_and_combo_arrows_are_preserved(app,folders):
    import fitz
    from PySide2.QtWidgets import QStyleOptionComboBox, QStyle
    doc=fitz.open();page=doc.new_page()
    for x,colour in ((50,(1,0,0)),(180,(0,1,0)),(310,(0,0,1))):
        page.draw_rect(fitz.Rect(x,100,x+70,170),color=colour,fill=colour)
    data=doc.tobytes();doc.close()
    source,target=folders
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.show();window.viewer.open_data(data);window.viewer.zoom(1/window.viewer.scale);app.processEvents()
    original=window.viewer.label.pixmap().toImage()
    try:
        for theme in THEME_NAMES:
            set_theme(theme);app.processEvents()
            assert window.viewer.label.pixmap().toImage()==original
        set_theme('Longhorn Blue')
        dialog=SettingsDialog(window.settings,window);dialog.show();app.processEvents()
        combo=dialog.surface_combo
        option=QStyleOptionComboBox();combo.initStyleOption(option)
        area=combo.style().subControlRect(QStyle.CC_ComboBox,option,QStyle.SC_ComboBoxArrow,combo)
        pixels=combo.grab(area).toImage()
        dark=sum(1 for y in range(pixels.height()) for x in range(pixels.width())
                 if pixels.pixelColor(x,y).lightness()<100)
        assert dark>3
        dialog.reject()
    finally:window.close()
