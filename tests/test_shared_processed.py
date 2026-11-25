import json
import multiprocessing
import os
import time
from dataclasses import replace
from datetime import date
from pathlib import Path, PureWindowsPath
from zipfile import ZipFile

import pytest
from PySide2.QtCore import Qt

from edpd.config import Settings, ViewerSettings
from edpd.file_service import FileService
from edpd.locking import workspace_lock
from edpd.models import Day, Document, EDPDError
from edpd.processed_store import ProcessedStore
from edpd.shared_processed_store import PROTECTION, SharedProcessedStore, shared_packet_id
from edpd.ui.main_window import MainWindow
from edpd.ui.settings_dialog import SettingsDialog
from edpd.ui import main_window


def mark_in_process(source, target, key, barrier):
    store = SharedProcessedStore(source, target)
    barrier.wait(15)
    for attempt in range(100):
        try:
            store.set_processed(key, True)
            return
        except EDPDError as exc:
            if 'foglalt' not in str(exc):
                raise
            time.sleep(.02)
    raise RuntimeError('could not acquire the workspace lock')


def wait_for(app, condition):
    deadline = time.monotonic() + 12
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert condition()


def make_day(root):
    zip_path = root / '20260105.zip'
    return Day(date(2026, 1, 5), (zip_path,),
               (Document(zip_path, 'folder/sample.pdf', 'sample.pdf', 10, 123),))


def test_shared_setting_and_backwards_compatibility(app, folders, tmp_path):
    source, target = folders
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}', encoding='utf-8')
    assert not Settings().shared_workspace
    assert not Settings.load(settings_file).shared_workspace
    dialog = SettingsDialog(Settings(source=str(source), target=str(target)), None)
    assert dialog.shared_workspace.text() == 'Ez egy közös mappa'
    assert not dialog.shared_workspace.isChecked()
    dialog.shared_workspace.setChecked(True)
    dialog.result_settings().save(settings_file)
    assert Settings.load(settings_file).shared_workspace is True
    assert not hasattr(SettingsDialog(ViewerSettings.load(settings_file), None), 'shared_workspace')
    assert not (target / '.edpd-processed.json').exists()
    settings_file.write_text('{"shared_workspace": "true"}', encoding='utf-8')
    with pytest.raises(ValueError):
        Settings.load(settings_file)


def test_packet_identity_is_independent_of_path_but_checks_metadata():
    mapped = make_day(PureWindowsPath(r'H:\PostaEDPB\10_Komárom'))
    unc = make_day(PureWindowsPath(r'\\server\posta\10_Komárom'))
    assert shared_packet_id(mapped) == shared_packet_id(unc)
    changed = replace(unc, documents=(replace(unc.documents[0], crc=456),))
    assert shared_packet_id(changed) != shared_packet_id(mapped)
    assert shared_packet_id(replace(mapped, date=date(2026, 1, 6))) != shared_packet_id(mapped)
    assert shared_packet_id(replace(mapped, archives=(Path('20260105-other.zip'),))) != shared_packet_id(mapped)


def test_shared_creation_backup_and_pdf_cleanup(folders):
    source, target = folders
    day = make_day(source)
    local = ProcessedStore(source, target)
    local.set_processed(day, True)
    store = SharedProcessedStore(source, target)
    assert not store.primary.exists()
    store.prepare()
    assert not store.inspect().packets
    initial = json.loads(store.primary.read_text(encoding='utf-8'))
    assert initial['schema'] == 2 and initial['revision'] == 0 and initial['packets'] == []
    key = shared_packet_id(day)
    assert store.set_processed(key, True).packets == {key}
    assert store.set_processed(key, True).packets == {key}
    assert json.loads(store.primary.read_text(encoding='utf-8'))['revision'] == 1
    assert json.loads(store.backup.read_text(encoding='utf-8')) == initial
    if os.name == 'nt':
        for path in (store.primary, store.backup):
            assert path.stat().st_file_attributes & PROTECTION == PROTECTION
    (target / 'sample.pdf').write_bytes(b'test')
    service = FileService(source, target)
    assert service.deletion_plan() == {'sample.pdf'}
    service.delete(confirmed=True, expected_names={'sample.pdf'})
    assert set(p.name for p in target.iterdir()) == {
        store.primary.name, store.backup.name, '.edpd-operation.lock',
    }
    assert store.inspect().packets == {key} and len(local.read()) == 1


def test_parallel_process_writes_and_stale_remove(folders):
    source, target = folders
    store = SharedProcessedStore(source, target)
    store.prepare()
    ctx = multiprocessing.get_context('spawn')
    barrier = ctx.Barrier(2)
    keys = 'a' * 64, 'b' * 64
    workers = [ctx.Process(target=mark_in_process, args=(source, target, key, barrier)) for key in keys]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(20)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
    assert store.inspect().packets == set(keys)
    other = SharedProcessedStore(source, target)
    assert other.set_processed(keys[0], False).packets == {keys[1]}
    assert store.set_processed(keys[0], False).packets == {keys[1]}
    original = store.primary.read_bytes()
    with workspace_lock(target), pytest.raises(EDPDError, match='foglalt'):
        other.set_processed(keys[1], False)
    assert store.primary.read_bytes() == original


def overwrite_for_test(path, data):
    if os.name == 'nt':
        from edpd.shared_processed_store import windows_attributes
        windows_attributes(path, 0)
    path.write_bytes(data)


def test_damage_recovery_missing_state_and_backup(folders):
    source, target = folders
    store = SharedProcessedStore(source, target)
    store.prepare()
    key = '1' * 64
    store.set_processed(key, True)
    store.set_processed('2' * 64, True)
    damaged = b'{"schema":99}'
    overwrite_for_test(store.primary, damaged)
    state = store.inspect()
    assert state.error and state.recovery
    with pytest.raises(EDPDError):
        store.set_processed(key, False)
    assert store.primary.read_bytes() == damaged
    assert store.restore(state.recovery).packets == {key}
    assert (target / '.edpd-processed.damaged').read_bytes() == damaged
    with pytest.raises(EDPDError, match='megváltozott'):
        store.restore(state.recovery)
    overwrite_for_test(store.backup, b'{}')
    state = store.inspect()
    assert state.error and state.recovery is None
    with pytest.raises(EDPDError):
        store.set_processed(key, False)
    assert store.backup.read_bytes() == b'{}'
    overwrite_for_test(store.primary, b'')
    store.primary.unlink()
    missing = store.inspect()
    assert missing.error and missing.recovery is None
    with pytest.raises(EDPDError):
        store.set_processed(key, True)
    assert not store.primary.exists()


def test_failed_primary_replace_preserves_last_state_and_protection(folders, monkeypatch):
    from edpd import shared_processed_store as module
    source, target = folders
    store = SharedProcessedStore(source, target)
    store.prepare()
    original_replace = os.replace

    def fail_primary(temporary, destination):
        if destination == store.primary:
            raise PermissionError('simulated network write failure')
        return original_replace(temporary, destination)

    monkeypatch.setattr(module.os, 'replace', fail_primary)
    with pytest.raises(PermissionError):
        store.set_processed('c' * 64, True)
    assert not store.inspect().error
    assert store.inspect().packets == set()
    assert list(target.glob('*.tmp')) == []
    if os.name == 'nt':
        assert store.primary.stat().st_file_attributes & PROTECTION == PROTECTION


def test_two_managers_poll_only_marks_and_switch_back_to_local(app, folders, pdf_bytes, monkeypatch):
    source, target = folders
    for day_number in (5, 6):
        with ZipFile(source / f'202601{day_number:02}.zip', 'w') as archive:
            archive.writestr(f'{day_number}.pdf', pdf_bytes)
    settings = Settings(source=str(source), target=str(target), history_days=None)
    first = MainWindow(settings, auto_refresh=False)
    second = MainWindow(replace(settings), auto_refresh=False)

    def configure(window, checked):
        class Dialog:
            def __init__(self, current, parent):
                self.current = current

            def exec_(self):
                return True

            def result_settings(self):
                return replace(self.current, shared_workspace=checked)

        monkeypatch.setattr(main_window, 'SettingsDialog', Dialog)
        window.configure()
        wait_for(app, lambda: not window.jobs and window.settings.shared_workspace == checked
                 and window.mark_error != 'Feldolgozottsági jelzők betöltése…')

    try:
        first.apply_snapshot(first.snapshot())
        second.apply_snapshot(second.snapshot())
        row = 1
        day = first.days[row]
        local = ProcessedStore(source, target)
        local.set_processed(day, True)
        first.apply_snapshot(first.snapshot())
        assert first.day_table.item(row, 4).data(Qt.UserRole) == 'processed'
        configure(first, True)
        configure(second, True)
        assert first.mark_timer.isActive() and first.mark_timer.interval() == 15_000
        assert not first.processed and not second.processed
        second.day_table.selectRow(0)
        second.viewer.open_data(pdf_bytes)
        second.viewer.move(1)
        preview = second.viewer.pdf
        with monkeypatch.context() as patch:
            def unexpected(*args, **kwargs):
                pytest.fail('Shared mark polling scanned an archive or rendered a PDF')

            patch.setattr(second.zip, 'catalogue', unexpected)
            patch.setattr(second.zip, 'scan', unexpected)
            patch.setattr(second.viewer.pdf, 'render', unexpected)
            first.mark_day(day)
            wait_for(app, lambda: not first.jobs)
            second.mark_timer.timeout.emit()
            wait_for(app, lambda: not second.jobs)
            assert second.day_table.currentRow() == 0
            assert second.viewer.pdf is preview and second.viewer.page == 1
            assert second.day_table.item(row, 4).data(Qt.UserRole) == 'processed'
            store = SharedProcessedStore(source, target)
            overwrite_for_test(store.primary, b'{}')
            second.poll_shared_marks()
            wait_for(app, lambda: not second.jobs)
            assert second.mark_error
            assert second.day_table.item(row, 4).data(Qt.UserRole) == 'processed'
            assert not second.processed_action.isEnabled()
            assert not second.restore_marks_button.isHidden()
            with monkeypatch.context() as confirm:
                confirm.setattr(main_window.QMessageBox, 'question', lambda *args: main_window.QMessageBox.Yes)
                second.restore_shared_marks()
                wait_for(app, lambda: not second.jobs)
            assert not second.mark_error and not second.processed
            second.mark_day(day)
            wait_for(app, lambda: not second.jobs)
        configure(first, False)
        assert not first.mark_timer.isActive()
        assert first.day_table.item(row, 4).data(Qt.UserRole) == 'processed'
        assert SharedProcessedStore(source, target).inspect().packets == {shared_packet_id(day)}
        assert len(local.read()) == 1
    finally:
        second.viewer.clear()
        first.close()
        second.close()


def test_poll_reuses_unchanged_state_without_reading_json(folders, monkeypatch):
    from edpd import shared_processed_store as module

    source, target = folders
    store = SharedProcessedStore(source, target)
    store.prepare()
    cached = store.inspect()

    def unexpected(*args):
        pytest.fail('Unchanged state was read again')

    monkeypatch.setattr(module, 'read_record', unexpected)
    assert store.inspect(cached) is cached


def test_missing_primary_is_only_restored_after_confirmation(folders):
    source, target = folders
    store = SharedProcessedStore(source, target)
    store.prepare()
    overwrite_for_test(store.primary, b'')
    store.primary.unlink()
    state = store.inspect()
    assert state.error and state.packets is None and state.recovery
    with pytest.raises(EDPDError):
        store.set_processed('a' * 64, True)
    assert not store.primary.exists()
    assert store.restore(state.recovery).packets == set()


def test_shared_state_writes_never_enter_source(folders):
    source, _ = folders
    with pytest.raises(EDPDError):
        SharedProcessedStore(source, source).prepare()
    assert list(source.iterdir()) == []
