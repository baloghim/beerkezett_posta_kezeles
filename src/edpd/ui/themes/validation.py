"""Synthetic EXE self-test only; never imported during normal application startup."""
import hashlib
import time
from dataclasses import replace
from pathlib import Path
from PySide2.QtCore import Qt, QCoreApplication, QEvent
from PySide2.QtGui import QPalette
from PySide2.QtWidgets import QApplication, QWidget, QStyleFactory
from . import manager, set_theme, THEME_NAMES
from .styles import stylesheet
from ..appearance import apply_style, current_style_name
from ..icons import manager as icon_manager, set_theme as set_icons, icon, THEME_NAMES as ICON_NAMES
from ..settings_dialog import SettingsDialog


def settle(app):
    for _ in range(4):app.processEvents()


def validate_surfaces(window, destination):
    app=QApplication.instance()
    output=Path(destination)
    output.mkdir(parents=True,exist_ok=True)
    original_surface,original_icons=manager().name,icon_manager().name
    original_style=current_style_name()
    original_size=window.size()
    original_minimum,original_maximum=window.minimumSize(),window.maximumSize()
    original_min,toolbar_min=window.minimumWidth(),window.viewer.toolbar.minimumWidth()
    viewer=window.viewer
    viewer.zoom(1.0/viewer.scale)
    settle(app)
    pixels=viewer.label.pixmap().toImage()
    data=viewer.pdf.data
    identity=icon('app').cacheKey()
    foreground=[window.day_table.item(row,0).foreground().color().name()
                for row in range(window.day_table.rowCount())]
    result={'surface_names':list(THEME_NAMES),'combinations':[],'viewports':[],
            'css_sha256':{name:hashlib.sha256(stylesheet(name).encode()).hexdigest() for name in THEME_NAMES[1:]},
            'qt_platform':app.platformName(),'device_pixel_ratio':app.primaryScreen().devicePixelRatio(),
            'screenshots':[]}
    try:
        for style in QStyleFactory.keys():
            for surface in THEME_NAMES:
                for icons in ICON_NAMES:
                    started=time.perf_counter()
                    apply_style(style,surface);set_icons(icons);settle(app)
                    assert current_style_name().lower()==style.lower()
                    assert manager().name==surface
                    assert bool(app.styleSheet())==(surface!=THEME_NAMES[0])
                    assert window.actions[0].icon().cacheKey()==icon('extract').cacheKey()
                    assert viewer.print_action.icon().cacheKey()==icon('print').cacheKey()
                    assert icon('app').cacheKey()==identity
                    assert viewer.label.pixmap().toImage()==pixels and viewer.pdf.data==data
                    assert viewer.fit_mode is None and abs(viewer.scale-1)<1e-7
                    assert [window.day_table.item(row,0).foreground().color().name()
                            for row in range(window.day_table.rowCount())]==foreground
                    result['combinations'].append({'qt_style':style,'surface':surface,'icons':icons,
                                                   'switch_ms':round((time.perf_counter()-started)*1000,3)})
        apply_style('Fusion','Alapértelmezett')
        settle(app)
        palette=QPalette(app.palette())
        widget_count=len(app.allWidgets())
        for _ in range(15):
            for surface in THEME_NAMES:set_theme(surface);settle(app)
        set_theme('Alapértelmezett');settle(app)
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        assert app.palette()==palette and app.styleSheet()==''
        assert all(widget.styleSheet()=='' for widget in window.findChildren(QWidget))
        assert len(app.allWidgets())<=widget_count+1
        assert not viewer.theme_title.isVisible()
        result['repeat_cycles']=15
        result['default_palette_restored']=True
        result['widget_growth']=len(app.allWidgets())-widget_count
        window.setMinimumWidth(0);viewer.toolbar.setMinimumWidth(0)
        for surface in THEME_NAMES:
            set_theme(surface);set_icons('Crystal SVG');settle(app)
            for width,height in ((1280,720),(1600,900),(1920,1080)):
                window.setFixedSize(width,height);settle(app)
                controls=(viewer.width_action,viewer.page_action,viewer.print_action,viewer.save_action)
                result['viewports'].append({'surface':surface,'requested':[width,height],
                    'actual':[window.width(),window.height()],
                    'labels':[action.text() for action in controls],
                    'visible':[viewer.toolbar.widgetForAction(action).isVisible() for action in controls]})
                assert window.split.count()==2 and window.left.count()==2
                assert all(viewer.toolbar.widgetForAction(action).toolButtonStyle()==Qt.ToolButtonTextBesideIcon for action in controls)
            window.setFixedSize(1600,900);settle(app)
            name={'Alapértelmezett':'default','Longhorn Blue':'blue','Longhorn Slate':'slate'}[surface]
            filename=f'{name}-crystal.png'
            assert window.grab().save(str(output/filename))
            result['screenshots'].append(filename)
        set_theme('Longhorn Blue');set_icons('Nuvola');settle(app)
        assert window.grab().save(str(output/'blue-nuvola.png'))
        result['screenshots'].append('blue-nuvola.png')
        set_icons('SE98');settle(app)
        assert window.grab().save(str(output/'blue-se98.png'))
        result['screenshots'].append('blue-se98.png')
        preview=replace(window.settings,ui_style='Longhorn Blue',qt_style='Fusion',
                        surface_theme='Longhorn Blue',icon_theme='SE98')
        dialog=SettingsDialog(preview,window);dialog.show();settle(app)
        assert dialog.grab().save(str(output/'blue-settings.png'))
        dialog.reject();dialog.deleteLater()
        result['screenshots'].append('blue-settings.png')
        result['pdf_bytes_preserved']=True
        result['pdf_pixels_preserved']=True
        result['semantic_foregrounds_preserved']=True
        return result
    finally:
        apply_style(original_style,original_surface);set_icons(original_icons)
        window.setMinimumSize(original_minimum);window.setMaximumSize(original_maximum)
        viewer.toolbar.setMinimumWidth(toolbar_min)
        window.resize(original_size)
