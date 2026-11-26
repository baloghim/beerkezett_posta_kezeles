import json
import os
from pathlib import Path

import pytest
from PySide2.QtWidgets import QFileDialog, QMessageBox

from edpd.config import Settings, ViewerSettings
from edpd.models import EDPDError
from edpd.pdf_export import check_pdf_save_directory, documents_directory
from edpd.ui.main_window import MainWindow
from edpd.ui.pdf_viewer import PDFViewer
from edpd.ui.settings_dialog import SettingsDialog
from edpd.ui.viewer_window import ViewerWindow
from test_ui import wait_for


@pytest.mark.parametrize('settings_type', [Settings, ViewerSettings])
def test_legacy_and_new_profiles_follow_current_documents(app, monkeypatch, tmp_path, settings_type):
    path = tmp_path / 'settings.json'
    documents = tmp_path / 'Dokumentumok'
    redirected = tmp_path / 'Átirányított Dokumentumok'
    monkeypatch.setattr('edpd.ui.settings_dialog.documents_directory', lambda: str(documents))
    for legacy in (False, True):
        if legacy:
            path.write_text(json.dumps({'source': 'archive'}), encoding='utf-8')
        with_dialog = SettingsDialog(settings_type.load(path), None)
        assert with_dialog.pdf_save_dir.text() == str(documents)
        settings = with_dialog.result_settings()
        assert settings.default_pdf_save_dir == ''
        with_dialog.close()
    settings.save(path)
    assert json.loads(path.read_text(encoding='utf-8'))['default_pdf_save_dir'] == ''
    monkeypatch.setattr('edpd.ui.settings_dialog.documents_directory', lambda: str(redirected))
    dialog = SettingsDialog(settings_type.load(path), None)
    assert dialog.pdf_save_dir.text() == str(redirected)
    dialog.close()


@pytest.mark.parametrize('window_type, settings_type', [(MainWindow, Settings), (ViewerWindow, ViewerSettings)])
def test_settings_save_updates_open_viewer_and_persists(app, monkeypatch, tmp_path, folders, window_type, settings_type):
    source, target = folders
    original, chosen = (tmp_path / name for name in ('Első mappa', 'Másik mappa'))
    original.mkdir()
    chosen.mkdir()
    kwargs = {'target': str(target)} if settings_type is Settings else {}
    settings = settings_type(source=str(source), default_pdf_save_dir=str(original), **kwargs)
    window = window_type(settings, auto_refresh=False)
    assert window.viewer.default_pdf_save_dir == str(original)

    def choose(dialog):
        monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(chosen))
        dialog.browse(dialog.pdf_save_dir)
        return dialog.Accepted

    monkeypatch.setattr(SettingsDialog, 'exec_', choose)
    try:
        window.configure()
        wait_for(app, lambda: not window.jobs)
        assert window.viewer.default_pdf_save_dir == str(chosen)
        assert settings_type.load().default_pdf_save_dir == str(chosen)

        errors = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))

        def choose_protected(dialog):
            dialog.pdf_save_dir.setText(str(source))
            return dialog.Accepted

        monkeypatch.setattr(SettingsDialog, 'exec_', choose_protected)
        window.configure()
        wait_for(app, lambda: not window.jobs)
        message = errors[-1] if errors else window.statusBar().currentMessage()
        assert 'kívül' in message
        assert window.viewer.default_pdf_save_dir == str(chosen)
        assert settings_type.load().default_pdf_save_dir == str(chosen)
    finally:
        window.close()


def test_applications_store_distinct_windows_paths():
    manager = r'G:\Igazgatás\Mentett PDF-ek'
    viewer = r'\\server\share\Átirányított Dokumentumok'
    Settings(default_pdf_save_dir=manager).save()
    ViewerSettings(default_pdf_save_dir=viewer).save()
    assert Settings.load().default_pdf_save_dir == manager
    assert ViewerSettings.load().default_pdf_save_dir == viewer


def test_config_rejects_protected_or_missing_directories(folders, tmp_path):
    source, target = folders
    inside = target / 'Védett mappa'
    inside.mkdir()
    settings = Settings(source=str(source), target=str(target))
    for invalid in (source, inside, tmp_path / 'Hiányzó'):
        settings.default_pdf_save_dir = str(invalid)
        with pytest.raises(EDPDError):
            check_pdf_save_directory(settings)
    settings.default_pdf_save_dir = str(tmp_path)
    check_pdf_save_directory(settings)
    assert not (tmp_path / 'Hiányzó').exists()


def test_save_starts_in_current_documents_or_override(app, monkeypatch, tmp_path, pdf_bytes):
    normal, redirected, custom = (tmp_path / name for name in ('Dokumentumok', 'Átirányítva', 'Egyéni mappa'))
    for folder in (normal, redirected, custom):
        folder.mkdir()
    documents = normal
    monkeypatch.setattr('edpd.ui.pdf_viewer.documents_directory', lambda: str(documents))
    suggestions = []
    chosen = tmp_path / 'más néven.pdf'

    def choose(parent, title, start, *args, **kwargs):
        suggestions.append(Path(start))
        return (str(chosen), '') if len(suggestions) == 1 else ('', '')

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    viewer = PDFViewer()
    viewer.open_data(pdf_bytes, 'eredeti.pdf')
    try:
        viewer.save_current()
        wait_for(app, lambda: viewer.save_job is None)
        assert chosen.read_bytes() == pdf_bytes
        viewer.save_current()
        documents = redirected
        viewer.save_current()
        viewer.set_pdf_save_dir(str(custom))
        viewer.save_current()
        viewer.set_pdf_save_dir('')
        viewer.save_current()
        assert suggestions == [
            folder.resolve() / 'eredeti.pdf' for folder in (normal, normal, redirected, custom, redirected)
        ]
    finally:
        viewer.clear()
        viewer.close()


@pytest.mark.parametrize('custom', [False, True])
def test_missing_save_directory_warns_and_allows_alternative(app, monkeypatch, tmp_path, pdf_bytes, custom):
    unavailable = tmp_path / 'Nem elérhető'
    alternative = tmp_path / 'választott.pdf'
    monkeypatch.setattr('edpd.ui.pdf_viewer.documents_directory', lambda: str(unavailable))
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))

    def choose(parent, title, start, *args, **kwargs):
        assert start == 'eredeti.pdf'
        assert warnings and str(unavailable) in warnings[-1]
        return str(alternative), ''

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    viewer = PDFViewer()
    viewer.open_data(pdf_bytes, 'eredeti.pdf')
    if custom:
        viewer.set_pdf_save_dir(str(unavailable))
    try:
        viewer.save_current()
        wait_for(app, lambda: viewer.save_job is None)
        assert alternative.read_bytes() == pdf_bytes
        assert not unavailable.exists()
    finally:
        viewer.clear()
        viewer.close()


@pytest.mark.skipif(os.name != 'nt', reason='Windows Known Folder API')
def test_windows_documents_lookup_returns_absolute_path():
    assert Path(documents_directory()).is_absolute()
