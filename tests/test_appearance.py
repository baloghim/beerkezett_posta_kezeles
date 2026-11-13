import json

import pytest
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QDialogButtonBox, QLabel, QStyleFactory, QWidget

from edpd import __version__
from edpd.config import Settings
from edpd.ui.about_dialog import AboutDialog
from edpd.ui.appearance import apply_style
from edpd.ui.main_window import MainWindow
from edpd.ui.pdf_viewer import PDFViewer
from edpd.ui.settings_dialog import SettingsDialog
from test_ui import wait_for


@pytest.fixture(autouse=True)
def restore_style(app):
    original = app.style().objectName()
    yield
    apply_style(original)


@pytest.mark.parametrize('style', QStyleFactory.keys())
def test_available_styles_save_and_apply(app, folders, tmp_path, monkeypatch, style):
    source, target = folders
    settings = Settings(source=str(source), target=str(target))
    window = MainWindow(settings)
    window.show()
    wait_for(app, lambda: window.source_generation > 0 and not window.jobs)

    def choose(dialog):
        assert [dialog.style_combo.itemData(i) for i in range(dialog.style_combo.count())] == QStyleFactory.keys()
        dialog.style_combo.setCurrentIndex(dialog.style_combo.findData(style))
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(SettingsDialog, 'exec_', choose)
    window.configure()
    wait_for(app, lambda: window.settings.qt_style == style and not window.jobs)
    assert app.style().objectName().lower() == style.lower()
    assert Settings.load().qt_style == style
    apply_style('Unavailable style')
    assert apply_style(Settings.load().qt_style).lower() == style.lower()
    assert app.styleSheet() == ''
    assert all(widget.styleSheet() == '' for widget in window.findChildren(QWidget))
    assert window.split.count() == 2 and window.left.count() == 2
    window.close()


def test_cancel_preserves_style_and_configuration(app, tmp_path):
    apply_style('Fusion')
    settings = Settings(qt_style='Fusion')
    path = tmp_path / 'settings.json'
    settings.save(path)
    before = path.read_bytes()
    dialog = SettingsDialog(settings, None)
    alternative = next(key for key in QStyleFactory.keys() if key.lower() != 'fusion')
    dialog.style_combo.setCurrentText(alternative)
    buttons = dialog.findChild(QDialogButtonBox)
    buttons.button(QDialogButtonBox.Cancel).click()
    assert dialog.result() == dialog.Rejected
    assert settings.qt_style == 'Fusion'
    assert app.style().objectName() == 'fusion'
    assert path.read_bytes() == before


def test_old_configuration_and_unavailable_style(app, tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{}')
    assert Settings.load(path).qt_style == 'Fusion'
    path.write_text(json.dumps({'qt_style': 'Unavailable style'}))
    assert apply_style(Settings.load(path).qt_style) == 'fusion'
    dialog = SettingsDialog(Settings.load(path), None)
    assert dialog.style_combo.currentText().lower() == 'fusion'
    dialog.reject()


@pytest.mark.parametrize('saved, expected', [('Windows', 'windows'), ('Missing style', 'fusion')])
def test_entrypoint_restores_style_in_new_process(tmp_path, saved, expected):
    import os
    import subprocess
    import sys
    settings = Settings(qt_style=saved)
    settings.save()
    code = '''
import sys
expected = sys.argv.pop()
from PySide2.QtCore import QTimer
from PySide2.QtWidgets import QApplication, QWidget
import edpd.ui.main_window
class Probe(QWidget):
    def __init__(self, settings, **kwargs):
        super().__init__()
        app = QApplication.instance()
        assert app.style().objectName() == expected
        assert app.styleSheet() == ''
        self.exit_timer = QTimer(self)
        self.exit_timer.timeout.connect(app.quit)
        self.exit_timer.start(100)
edpd.ui.main_window.MainWindow = Probe
from edpd.main import main
main()
'''
    result = subprocess.run([sys.executable, '-c', code, expected], env=os.environ.copy(),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_failed_settings_save_keeps_running_style(app, folders, tmp_path, monkeypatch):
    from PySide2.QtWidgets import QMessageBox
    import edpd.ui.main_window as main_window
    source, target = folders
    apply_style('Fusion')
    window = MainWindow(Settings(source=str(source), target=str(target)))
    window.show()
    wait_for(app, lambda: window.source_generation > 0 and not window.jobs)
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))

    def choose(dialog):
        dialog.style_combo.setCurrentText('Windows')
        return dialog.Accepted

    def fail(settings):
        raise OSError('Teszt: nem menthető')

    monkeypatch.setattr(SettingsDialog, 'exec_', choose)
    original_save = Settings.save
    def fail_candidate(settings, *args, **kwargs):
        if settings.qt_style == 'Windows':
            fail(settings)
        return original_save(settings, *args, **kwargs)
    monkeypatch.setattr(Settings, 'save', fail_candidate)
    window.configure()
    wait_for(app, lambda: errors and not window.jobs)
    assert window.settings.qt_style == 'Fusion'
    assert app.style().objectName() == 'fusion'
    window.close()
    assert Settings.load().qt_style == 'Fusion'


def test_about_button_labels_and_dialog(app, folders, tmp_path, monkeypatch):
    source, target = folders
    window = MainWindow(Settings(source=str(source), target=str(target)))
    window.show()
    wait_for(app, lambda: window.source_generation > 0 and not window.jobs)
    labels = [label.text() for label in window.findChildren(QLabel)]
    assert 'EDPD mappa tartalma' in labels
    assert 'Napi csomagok (ZIP)' not in labels
    assert window.actions[1].text() == 'Kijelölt nap fájljainak törlése'
    assert window.actions[1].toolTip() == 'Kijelölt nap fájljainak törlése'
    toolbar = window.main_toolbar
    assert toolbar.widgetForAction(toolbar.actions()[-1]) is window.toolbar_controls
    assert window.toolbar_controls.layout().itemAt(1).widget() is window.about_button
    assert window.about_button.toolButtonStyle() == Qt.ToolButtonIconOnly
    assert not window.about_button.icon().isNull()
    assert window.about_button.toolTip() == 'Névjegy'
    opened = []

    def inspect(dialog):
        opened.append(dialog)
        assert __version__ in dialog.info.toHtml()
        assert 'https://github.com/baloghim/beerkezett_posta_kezeles' in dialog.info.toHtml()
        assert dialog.info.openExternalLinks()
        assert 'jogtulajdonos még nem választott' in dialog.info.toHtml()
        assert dialog.style().objectName() == app.style().objectName()
        return dialog.Accepted

    monkeypatch.setattr(AboutDialog, 'exec_', inspect)
    window.about_button.click()
    assert len(opened) == 1
    for width in (800, 1600):
        window.resize(width, 900)
        app.processEvents()
        assert window.about_button.isVisible()
        assert window.about_button.geometry().right() > window.toolbar_controls.width() - 40
    window.close()


def test_pdf_fit_width_reopen_resize_and_full_page(app, pdf_bytes, monkeypatch):
    from PySide2.QtWidgets import QMessageBox
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    viewer = PDFViewer()
    viewer.resize(1000, 700)
    viewer.show()
    app.processEvents()
    viewer.open_data(pdf_bytes)
    app.processEvents()
    assert viewer.fit_mode == 'width' and viewer.width_action.isChecked()
    initial = viewer.label.pixmap().width()
    viewer.resize(1200, 800)
    wait_for(app, lambda: viewer.label.pixmap().width() > initial)
    rect = viewer.pdf.document[0].rect
    assert viewer.label.pixmap().width() == pytest.approx(viewer.scroll.viewport().width() - 24, abs=2)
    assert viewer.label.pixmap().width() / viewer.label.pixmap().height() == pytest.approx(rect.width / rect.height, abs=0.01)
    viewer.page_action.trigger()
    app.processEvents()
    assert viewer.fit_mode == 'page' and viewer.page_action.isChecked()
    assert not viewer.width_action.isChecked()
    assert viewer.label.pixmap().height() <= viewer.scroll.viewport().height()
    assert viewer.label.pixmap().width() <= viewer.scroll.viewport().width()
    viewer.width_action.trigger()
    assert viewer.fit_mode == 'width'
    viewer.move(2)
    assert viewer.page == 2
    viewer.zoom(1.25)
    assert viewer.fit_mode is None
    assert not viewer.width_action.isChecked() and not viewer.page_action.isChecked()
    viewer.open_data(pdf_bytes)
    assert viewer.page == 0 and viewer.fit_mode == 'width'
    assert viewer.width_action.isChecked() and viewer.print_action.isEnabled()
    assert viewer.width_action.toolTip() and viewer.page_action.toolTip()
    viewer.pdf.close()
    viewer.close()
    app.processEvents()
    assert not errors
