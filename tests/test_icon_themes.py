import hashlib
import json
from pathlib import Path
import pytest
from PySide2.QtGui import QImage
from PySide2.QtWidgets import QWidget
from edpd.config import Settings
from edpd.ui.icons import ASSETS, THEME_NAMES, IconThemeManager, icon, manager, set_theme, ThemedMenu
from edpd.ui.main_window import MainWindow
from edpd.ui.pdf_viewer import SpacedToolButton
from edpd.ui.settings_dialog import SettingsDialog
from test_ui import wait_for


@pytest.fixture(autouse=True)
def reset_theme(app):
    set_theme('Crystal SVG')
    yield
    set_theme('Crystal SVG')


def test_choices_defaults_persistence_and_unavailable_theme(app,tmp_path):
    settings=Settings()
    assert settings.icon_theme=='Crystal SVG'
    dialog=SettingsDialog(settings,None)
    assert tuple(dialog.icon_combo.itemText(i) for i in range(dialog.icon_combo.count()))==THEME_NAMES
    assert dialog.icon_combo.currentText()=='Crystal SVG'
    dialog.icon_combo.setCurrentText('Papirus')
    candidate=dialog.result_settings()
    candidate.save(tmp_path/'settings.json')
    assert Settings.load(tmp_path/'settings.json').icon_theme=='Papirus'
    assert set_theme('missing')=='Crystal SVG'
    dialog.reject()


@pytest.mark.parametrize('theme',THEME_NAMES)
def test_real_assets_have_recorded_origins_and_distinct_pixels(app,theme):
    metadata=json.loads((ASSETS/'themes.json').read_text())['themes'][theme]
    set_theme(theme)
    for role in ('extract','delete','clear','refresh','settings','about','first','previous','next','last',
                 'zoom_in','zoom_out','width','page','print','save','pdf','zip','warning'):
        assert not icon(role).pixmap(22,22).isNull(),(theme,role)
    if theme!='Crystal SVG':
        for role,record in metadata['icons'].items():
            original=ASSETS/'themes'/metadata['id']/'original'/record['original']
            assert hashlib.sha256(original.read_bytes()).hexdigest()==record['sha256']
            for size in (22,40):
                image=QImage(str(ASSETS/'themes'/metadata['id']/str(size)/(role+'.png')))
                assert image.width()==image.height()==size
        own=icon('refresh').pixmap(22,22).toImage()
        set_theme('Crystal SVG')
        assert own!=icon('refresh').pixmap(22,22).toImage()


def test_missing_role_uses_crystal_then_qt(app,tmp_path):
    set_theme('Nuvola')
    nuvola=icon('fit_width')
    assert manager().sources['width']=='Crystal SVG'
    set_theme('Crystal SVG')
    assert nuvola.pixmap(22,22).toImage()==icon('width').pixmap(22,22).toImage()
    (tmp_path/'themes.json').write_text('{"themes":{}}')
    fallback=IconThemeManager(tmp_path)
    assert fallback.set_theme('Papirus')=='Crystal SVG'
    assert not fallback.icon('pdf_save').isNull()
    assert fallback.sources['save']=='Qt standard'


def test_all_visible_roles_switch_without_reloading_data(app,folders,monkeypatch):
    source,target=folders
    (target/'test.pdf').write_bytes(b'synthetic')
    window=MainWindow(Settings(source=str(source),target=str(target)))
    window.show()
    wait_for(app,lambda:window.source_generation>0 and not window.jobs)
    app_id=icon('app').cacheKey()
    main_before=window.actions[0].icon().cacheKey()
    pdf_before=window.viewer.print_action.icon().cacheKey()
    list_before=window.docs_table.item(0,1).icon().cacheKey()
    generation=window.source_generation
    menu=ThemedMenu(window)
    menu_action=menu.addAction(icon('zip'),'ZIP')
    menu_action.setProperty('icon_role','zip')
    def choose(dialog):
        dialog.icon_combo.setCurrentText('Papirus')
        return dialog.Accepted
    monkeypatch.setattr(SettingsDialog,'exec_',choose)
    import edpd.ui.main_window as mw
    monkeypatch.setattr(mw,'check_settings',lambda *_:pytest.fail('Appearance-only change accessed network'))
    window.configure()
    wait_for(app,lambda:not window.jobs)
    assert Settings.load().icon_theme=='Papirus'
    assert window.actions[0].icon().cacheKey()!=main_before
    assert window.viewer.print_action.icon().cacheKey()!=pdf_before
    assert window.docs_table.item(0,1).icon().cacheKey()!=list_before
    assert menu_action.icon().cacheKey()==icon('zip').cacheKey()
    assert icon('app').cacheKey()==app_id
    assert window.source_generation==generation
    spaces=window.viewer.toolbar.findChildren(QWidget,'pdf-group-space')
    assert len(spaces)==5 and all(s.width()==6 for s in spaces)
    for action in (window.viewer.print_action,window.viewer.save_action):
        button=window.viewer.toolbar.widgetForAction(action)
        assert isinstance(button,SpacedToolButton)
        assert button.defaultAction() is action
    window.close()


def test_spaced_buttons_actually_paint_the_icon(app):
    from PySide2.QtCore import Qt, QSize
    from PySide2.QtGui import QIcon
    button=SpacedToolButton()
    button.setText('Nyomtatás')
    button.setIconSize(QSize(22,22))
    button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setIcon(icon('print'))
    button.setFixedSize(180,40)
    button.show()
    app.processEvents()
    with_icon=button.grab().toImage()
    button.setIcon(QIcon())
    app.processEvents()
    without_icon=button.grab().toImage()
    assert with_icon!=without_icon
    button.close()
