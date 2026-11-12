import threading
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
from PySide2.QtCore import QTimer
from PySide2.QtGui import QColor, QPalette
from PySide2.QtWidgets import QMessageBox
from edpd.completion_service import CompletionStore, day_identity
from edpd.config import Settings
from edpd.file_service import FileService
from edpd.models import Capabilities
from edpd.ui.main_window import MainWindow
from edpd.ui.settings_dialog import SettingsDialog
from edpd.zip_service import ZipService

TODAY = date(2026, 11, 12)


def wait(app, condition, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError('Nem fejeződött be a háttérművelet')


def put_zip(source, when, names, data):
    path = source / f'{when:%Y%m%d}_HIVATAL.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name in names:
            archive.writestr(name, data)
    return path


def setup_window(app, folders, tmp_path, monkeypatch):
    source, target = folders
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    settings = Settings(source=str(source), target=str(target), shared_data=str(tmp_path / 'shared'))
    window = MainWindow(settings, today_provider=lambda: TODAY)
    window.show()
    wait(app, lambda: bool(window.days) and not window.jobs)
    return window, errors


def test_whole_workspace_origins_day_navigation_and_pdf_retained(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, ['today.pdf'], pdf_bytes)
    put_zip(source, TODAY - timedelta(days=1), ['yesterday.pdf'], pdf_bytes)
    put_zip(source, TODAY - timedelta(days=100), ['old.pdf'], pdf_bytes)
    for name in ['today.pdf', 'yesterday.pdf', 'old.pdf', 'unknown.pdf']:
        (target / name).write_bytes(pdf_bytes)
    window, errors = setup_window(app, folders, tmp_path, monkeypatch)
    assert window.origin_pending and not window.origin_requested
    assert window.docs_table.item(window.work_keys.index('old.pdf'), 2).text() == 'Ismeretlen'
    window.origin_button.click()
    wait(app, lambda: not window.origin_pending and not window.jobs)
    assert len(window.days) == 2
    assert window.docs_table.rowCount() == 4
    row = window.work_keys.index('today.pdf')
    window.docs_table.selectRow(row)
    wait(app, lambda: window.viewer.pdf is not None and not window.jobs)
    document = window.viewer.pdf
    window.viewer.move(2)
    window.day_table.selectRow(1)
    assert window.docs_table.rowCount() == 4
    assert window.viewer.pdf is document and window.viewer.page == 2
    assert window.docs_table.item(window.work_keys.index('old.pdf'), 2).text() == '2026.08.04.'
    assert window.docs_table.item(window.work_keys.index('unknown.pdf'), 2).text() == 'Ismeretlen'
    window.refresh()
    wait(app, lambda: not window.jobs)
    assert window.viewer.pdf is document and window.viewer.page == 2
    assert not errors
    window.close()


def test_done_mark_visual_priority_revoke_and_no_pdf_changes(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, ['a.pdf', 'b.pdf'], pdf_bytes)
    window, errors = setup_window(app, folders, tmp_path, monkeypatch)
    assert window.day_table.item(0, 3).text() == 'Nincs kicsomagolva'
    assert not window.day_table.item(0, 0).font().bold()
    day = window.current_day()
    service = FileService(source, target)
    service.extract(day)
    window.refresh()
    wait(app, lambda: not window.jobs)
    assert window.day_table.item(0, 0).font().bold()
    assert window.day_table.item(0, 0).foreground().color() == QColor('#000000')
    before = {p.name: p.read_bytes() for p in target.glob('*.pdf')}
    window.toggle_done()
    wait(app, lambda: not window.jobs)
    assert window.day_table.item(0, 3).text() == 'Elvégezve'
    assert window.mark_action.text() == 'Jelölés visszavonása'
    for col in range(4):
        assert window.day_table.item(0, col).foreground().color() == QColor('#167235')
    assert window.day_table.palette().color(QPalette.HighlightedText) == QColor('white')
    assert before == {p.name: p.read_bytes() for p in target.glob('*.pdf')}
    service.delete(day, confirmed=True, expected_names=service.deletion_plan(day))
    window.refresh()
    wait(app, lambda: not window.jobs)
    assert window.day_table.item(0, 3).text() == 'Elvégezve'
    assert window.docs_table.rowCount() == 0
    window.toggle_done()
    wait(app, lambda: not window.jobs)
    assert window.day_table.item(0, 3).text() == 'Nincs kicsomagolva'
    assert window.mark_action.text() == 'Elvégezve jelölés'
    assert not errors
    window.close()


def test_partial_state_and_changed_shared_marks_seen_on_refresh(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, ['a.pdf', 'b.pdf'], pdf_bytes)
    (target / 'a.pdf').write_bytes(pdf_bytes)
    window, errors = setup_window(app, folders, tmp_path, monkeypatch)
    assert window.day_table.item(0, 3).text() == 'Részben kicsomagolva'
    assert window.day_table.item(0, 0).foreground().color() == QColor('#885000')
    CompletionStore(tmp_path / 'shared', source, target).set_done(window.current_day(), True)
    window.refresh()
    wait(app, lambda: not window.jobs)
    assert window.day_table.item(0, 3).text() == 'Elvégezve'
    assert not errors
    window.close()


def test_daily_delete_dialog_exact_count_and_mark_independence(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, [f'a{i}.pdf' for i in range(6)], pdf_bytes)
    put_zip(source, TODAY - timedelta(days=1), ['other.pdf'], pdf_bytes)
    for name in [*(f'a{i}.pdf' for i in range(4)), 'other.pdf']:
        (target / name).write_bytes(pdf_bytes)
    window, errors = setup_window(app, folders, tmp_path, monkeypatch)
    messages = []
    def yes(*args):
        messages.append(args[2])
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', yes)
    store = CompletionStore(tmp_path / 'shared', source, target)
    store.set_done(window.current_day(), True)
    window.refresh()
    wait(app, lambda: not window.jobs)
    window.delete(False)
    wait(app, lambda: window.docs_table.rowCount() == 1 and not window.jobs)
    assert '6 dokumentumból jelenleg 4' in messages[0]
    assert (target / 'other.pdf').exists()
    assert window.day_table.item(0, 3).text() == 'Elvégezve'
    assert not errors
    window.close()


def test_corrupt_shared_state_is_visible_and_disables_marking(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, _ = folders
    put_zip(source, TODAY, ['a.pdf'], pdf_bytes)
    shared = tmp_path / 'shared'
    shared.mkdir()
    (shared / 'completed.json').write_text('bad')
    window, errors = setup_window(app, folders, tmp_path, monkeypatch)
    assert not window.mark_action.isEnabled()
    assert window.shared_notice.isVisible()
    assert 'nem érhetők el' in window.shared_notice.text()
    assert window.actions[0].isEnabled()
    assert not errors  # Időzítőből nem nyitunk ismétlődő modális ablakot.
    window.close()


def test_settings_history_choices_and_viewer_mark_permission(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, ['a.pdf'], pdf_bytes)
    settings = Settings(source=str(source), target=str(target), shared_data=str(tmp_path / 'shared'))
    dialog = SettingsDialog(settings, None)
    assert [dialog.history.itemData(i) for i in range(dialog.history.count())] == [14, 30, 90, 180, None]
    for index, expected in enumerate([14, 30, 90, 180, None]):
        dialog.history.setCurrentIndex(index)
        assert dialog.result_settings().history_days == expected
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    window = MainWindow(settings, Capabilities.viewer(), today_provider=lambda: TODAY)
    window.show()
    wait(app, lambda: bool(window.days) and not window.jobs)
    assert not window.mark_action.isEnabled()
    window.toggle_done()
    assert not (tmp_path / 'shared').exists()
    assert not errors
    window.close()


def test_ui_stays_responsive_while_all_archives_are_scanned(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    put_zip(source, TODAY, ['a.pdf'], pdf_bytes)
    settings = Settings(source=str(source), target=str(target), shared_data=str(tmp_path / 'shared'), history_days=None)
    release, entered = threading.Event(), threading.Event()
    original = ZipService.scan
    def delayed(self, *args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise TimeoutError('Teszt nem oldotta fel a beolvasást')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(ZipService, 'scan', delayed)
    window = MainWindow(settings, today_provider=lambda: TODAY)
    window.show()
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    try:
        wait(app, lambda: entered.is_set() and len(ticks) >= 3)
        assert window.busy and not window.days
    finally:
        release.set()
        timer.stop()
    wait(app, lambda: bool(window.days) and not window.jobs)
    window.close()


def test_workspace_preview_survives_unavailable_source(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    (target / 'local.pdf').write_bytes(pdf_bytes)
    settings = Settings(source=str(source / 'unavailable'), target=str(target), shared_data=str(tmp_path / 'shared'))
    window = MainWindow(settings, today_provider=lambda: TODAY)
    window.show()
    wait(app, lambda: window.docs_table.rowCount() == 1 and not window.jobs)
    assert not window.days and window.access_error
    assert not window.actions[3].isEnabled()  # Elérés nélkül nincs módosítás.
    assert window.shared_notice.isVisible()
    window.docs_table.selectRow(0)
    wait(app, lambda: window.viewer.pdf is not None and not window.jobs)
    assert window.viewer.pdf.pages == 3
    assert (target / 'local.pdf').read_bytes() == pdf_bytes
    window.close()
