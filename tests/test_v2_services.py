import json
import multiprocessing
import os
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from edpd.config import Settings
from edpd.completion_service import CompletionStore, day_identity, validate_shared_directory
from edpd.file_service import FileService
from edpd.models import Capabilities, EDPDError
from edpd.paths import normalize_path
from edpd.zip_service import ZipService

TODAY = date(2026, 11, 12)


def make_zip(source, when=TODAY, suffix='A', entries=None):
    path = source / f'{when:%Y%m%d}_{suffix}.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in (entries or {'a.pdf': b'a'}).items():
            archive.writestr(name, data)
    return path


@pytest.mark.parametrize('period', [14, 30, 90, 180, None])
def test_calendar_filter_before_zip_open(folders, period, monkeypatch):
    source, _ = folders
    offsets = [0, 13, 14, 29, 30, 89, 90, 179, 180, -1]
    paths = [make_zip(source, TODAY - timedelta(days=n)) for n in offsets]
    real = zipfile.ZipFile
    opened = []
    def spy(path, *args, **kwargs):
        opened.append(Path(path))
        return real(path, *args, **kwargs)
    monkeypatch.setattr(zipfile, 'ZipFile', spy)
    def no_pdf_read(*args, **kwargs):
        raise AssertionError('Listázáskor PDF-tartalmat olvasott')
    monkeypatch.setattr(real, 'read', no_pdf_read)
    days = ZipService().scan(source, period, today=TODAY)
    expected = [p for n, p in zip(offsets, paths) if period is None or 0 <= n < period]
    assert set(opened) == set(expected)
    assert [d.date for d in days] == sorted((TODAY - timedelta(days=n) for n in offsets if period is None or 0 <= n < period), reverse=True)


def test_old_broken_archive_not_opened_in_filtered_scan(folders):
    source, _ = folders
    make_zip(source)
    (source / '20000101_bad.zip').write_bytes(b'broken')
    days = ZipService().scan(source, 14, today=TODAY)
    assert len(days) == 1 and not days[0].error


def test_persistent_origins_and_unknowns_without_repeat_archive_reads(folders, tmp_path, monkeypatch):
    source, target = folders
    make_zip(source, entries={'new.pdf': b'n'})
    old = TODAY - timedelta(days=100)
    old_path = make_zip(source, old, entries={'old.pdf': b'o'})
    (target / 'old.pdf').write_bytes(b'o')
    (target / 'foreign.pdf').write_bytes(b'x')
    files = {p.name.casefold(): p for p in target.iterdir()}
    service = ZipService(cache_dir=tmp_path / 'cache')
    entries = service.catalogue(source)
    service.scan(source, 14, today=TODAY, entries=entries)
    labels, pending, complete = service.origin_state(source, files, entries)
    assert labels['old.pdf'] == 'Ismeretlen' and not complete
    assert [p.path for p in pending] == [old_path]
    service.index_batch(pending)
    service.save()
    def fail_open(*args, **kwargs):
        raise AssertionError('Változatlan ZIP-et újranyitott')
    monkeypatch.setattr(zipfile, 'ZipFile', fail_open)
    restored = ZipService(cache_dir=tmp_path / 'cache')
    entries = restored.catalogue(source)
    restored.scan(source, 14, today=TODAY, entries=entries)
    labels, pending, complete = restored.origin_state(source, files, entries)
    assert complete and not pending
    assert labels == {'old.pdf': old.strftime('%Y.%m.%d.'), 'foreign.pdf': 'Ismeretlen'}


def test_origins_detect_ambiguity_and_invalidated_cache(folders, tmp_path):
    source, target = folders
    old = TODAY - timedelta(days=100)
    make_zip(source, entries={'a.pdf': b'a'})
    make_zip(source, old, entries={'a.pdf': b'a'})
    (target / 'a.pdf').write_bytes(b'a')
    files = {'a.pdf': target / 'a.pdf'}
    service = ZipService(cache_dir=tmp_path / 'cache')
    service.scan(source)
    entries = service.catalogue(source)
    labels, _, complete = service.origin_state(source, files, entries)
    assert complete and labels['a.pdf'].startswith('Többértelmű:')
    make_zip(source, old, entries={'different.pdf': b'longer'})
    entries = service.catalogue(source)
    labels, pending, complete = service.origin_state(source, files, entries)
    assert not complete and 'ellenőrzés alatt' in labels['a.pdf']
    service.index_batch(pending)
    labels, _, complete = service.origin_state(source, files, entries)
    assert complete and labels['a.pdf'] == TODAY.strftime('%Y.%m.%d.')


def test_corrupt_local_cache_is_rebuilt(folders, tmp_path):
    source, _ = folders
    make_zip(source)
    service = ZipService(cache_dir=tmp_path / 'cache')
    service.scan(source)
    service.save()
    service.cache_path.write_text('{not json')
    restored = ZipService(cache_dir=tmp_path / 'cache')
    assert restored.scan(source)[0].documents[0].name == 'a.pdf'


@pytest.mark.parametrize('value, expected', [
    ('H://PostaEDPB//Megye/', 'H:\\PostaEDPB\\Megye'),
    ('H:\\PostaEDPB\\Megye', 'H:\\PostaEDPB\\Megye'),
    ('//szerver/megosztas/mappa', '\\\\szerver\\megosztas\\mappa'),
    ('\\\\szerver\\megosztas\\mappa', '\\\\szerver\\megosztas\\mappa'),
    ('\\\\?\\UNC\\szerver\\megosztas\\mappa', '\\\\?\\UNC\\szerver\\megosztas\\mappa'),
])
def test_windows_paths_and_config_roundtrip(tmp_path, value, expected):
    assert normalize_path(value) == expected
    settings = Settings(source=value, shared_data='\\\\szerver\\kozos\\EDPD_appdata', history_days=90)
    path = tmp_path / 'settings.json'
    settings.save(path)
    loaded = Settings.load(path)
    assert loaded.source == expected and loaded.history_days == 90
    assert loaded.shared_data.startswith('\\\\szerver\\')


def test_old_configuration_defaults_and_invalid_history(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{"source":"H://PostaEDPB//Megye"}')
    settings = Settings.load(path)
    assert settings.history_days == 14 and settings.refresh_minutes == 15
    assert settings.source == 'H:\\PostaEDPB\\Megye'
    for value in [0, 15, True, '14']:
        path.write_text(json.dumps({'history_days': value}))
        with pytest.raises(ValueError):
            Settings.load(path)


def test_done_marks_persist_merge_revoke_and_ignore_pdf_operations(folders, tmp_path):
    source, target = folders
    make_zip(source, entries={'a.pdf': b'a', 'b.pdf': b'b'})
    make_zip(source, TODAY - timedelta(days=1), entries={'other.pdf': b'o'})
    days = ZipService().scan(source)
    store = CompletionStore(tmp_path / 'shared', source, target)
    assert store.read() == set()
    before_source = {p.name: p.read_bytes() for p in source.iterdir()}
    store.set_done(days[0], True)
    other_client = CompletionStore(tmp_path / 'shared', source, target)
    other_client.set_done(days[1], True)
    assert store.read() == {day_identity(d) for d in days}
    saved = (tmp_path / 'shared' / 'completed.json').read_bytes()
    service = FileService(source, target)
    service.extract(days[0])
    service.delete(days[0], confirmed=True, expected_names=service.deletion_plan(days[0]))
    (target / 'extra.pdf').write_bytes(b'x')
    service.delete(confirmed=True, expected_names=service.deletion_plan())
    assert (tmp_path / 'shared' / 'completed.json').read_bytes() == saved
    assert before_source == {p.name: p.read_bytes() for p in source.iterdir()}
    store.set_done(days[0], False)
    assert other_client.read() == {day_identity(days[1])}


def test_done_identity_distinguishes_offices_and_changed_packets(folders):
    source, _ = folders
    make_zip(source, suffix='HIVATAL_A')
    first = ZipService().scan(source)[0]
    make_zip(source, suffix='HIVATAL_B')
    combined = ZipService().scan(source)[0]
    assert day_identity(first) != day_identity(combined)
    make_zip(source, suffix='HIVATAL_A', entries={'a.pdf': b'changed'})
    assert day_identity(combined) != day_identity(ZipService().scan(source)[0])


def test_common_store_rejects_overlap_corruption_and_viewer(folders, tmp_path):
    source, target = folders
    make_zip(source)
    day = ZipService().scan(source)[0]
    for path in [source, source / 'appdata', target, target / 'appdata', source.parent]:
        with pytest.raises(EDPDError):
            validate_shared_directory(path, source, target)
    shared = tmp_path / 'shared'
    with pytest.raises(EDPDError):
        CompletionStore(shared, source, target, Capabilities.viewer()).set_done(day, True)
    assert not shared.exists()
    shared.mkdir()
    state = shared / 'completed.json'
    state.write_text('broken')
    store = CompletionStore(shared, source, target)
    with pytest.raises(EDPDError):
        store.read()
    with pytest.raises(EDPDError):
        store.set_done(day, True)
    assert state.read_text() == 'broken'


def test_failed_common_atomic_replace_preserves_existing_state(folders, tmp_path, monkeypatch):
    source, target = folders
    make_zip(source)
    day = ZipService().scan(source)[0]
    store = CompletionStore(tmp_path / 'shared', source, target)
    store.set_done(day, True)
    before = (tmp_path / 'shared' / 'completed.json').read_bytes()
    def fail(*args):
        raise OSError('Megszakadt kapcsolat')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        store.set_done(day, False)
    assert (tmp_path / 'shared' / 'completed.json').read_bytes() == before
    assert not list((tmp_path / 'shared').glob('*.tmp'))


def mark_worker(source, target, shared, selected_date, barrier, results):
    try:
        day = ZipService().scan(source, dates={selected_date})[0]
        store = CompletionStore(shared, source, target)
        barrier.wait(timeout=10)
        for attempt in range(30):
            try:
                store.set_done(day, True)
                results.put('ok')
                return
            except EDPDError as exc:
                if 'foglalt' not in str(exc):
                    raise
                time.sleep(0.03)
        results.put('lock timeout')
    except Exception as exc:
        results.put(repr(exc))


def test_two_processes_merge_common_marks_without_lost_updates(folders, tmp_path):
    source, target = folders
    make_zip(source)
    make_zip(source, TODAY - timedelta(days=1))
    days = ZipService().scan(source)
    shared = tmp_path / 'shared'
    shared.mkdir()
    context = multiprocessing.get_context('spawn')
    barrier, results = context.Barrier(2), context.Queue()
    processes = [context.Process(target=mark_worker, args=(source, target, shared, day.date, barrier, results)) for day in days]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            assert process.exitcode == 0
        assert [results.get(timeout=5) for _ in processes] == ['ok', 'ok']
        assert CompletionStore(shared, source, target).read() == {day_identity(d) for d in days}
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        results.close()


def test_daily_deletion_exact_subset_preserves_other_days_and_mark(folders, tmp_path):
    source, target = folders
    make_zip(source, entries={f'a{i}.pdf': str(i).encode() for i in range(6)})
    make_zip(source, TODAY - timedelta(days=100), entries={'other.pdf': b'o'})
    day = ZipService().scan(source, 14, today=TODAY)[0]
    for index in range(4):
        (target / f'a{index}.pdf').write_bytes(str(index).encode())
    (target / 'other.pdf').write_bytes(b'o')
    (target / 'keep.csv').write_text('keep')
    store = CompletionStore(tmp_path / 'shared', source, target)
    store.set_done(day, True)
    service = FileService(source, target)
    names = service.deletion_plan(day)
    assert names == {f'a{i}.pdf' for i in range(4)}
    service.delete(day, confirmed=True, expected_names=names)
    assert (target / 'other.pdf').read_bytes() == b'o'
    assert (target / 'keep.csv').exists()
    assert not list(target.glob('a*.pdf'))
    assert day_identity(day) in store.read()


def test_hidden_old_archive_collision_blocks_daily_deletion(folders):
    source, target = folders
    make_zip(source, entries={'shared.pdf': b'a'})
    make_zip(source, TODAY - timedelta(days=200), entries={'shared.pdf': b'a'})
    day = ZipService().scan(source, 14, today=TODAY)[0]
    (target / 'shared.pdf').write_bytes(b'a')
    with pytest.raises(EDPDError, match='Több nap'):
        FileService(source, target).deletion_plan(day)
    assert (target / 'shared.pdf').exists()


def test_common_store_retries_transient_windows_sharing_violation(folders, tmp_path, monkeypatch):
    source, target = folders
    make_zip(source)
    day = ZipService().scan(source)[0]
    store = CompletionStore(tmp_path / 'shared', source, target)
    store.set_done(day, True)
    original, attempts = os.replace, []
    def temporarily_open(*args):
        attempts.append(1)
        if len(attempts) == 1:
            error = PermissionError('Átmenetileg másik olvasó nyitva tartja')
            error.winerror = 32
            raise error
        return original(*args)
    monkeypatch.setattr(os, 'replace', temporarily_open)
    store.set_done(day, False)
    assert store.read() == set() and len(attempts) == 2


def test_mutations_reuse_checked_historical_metadata_but_reread_selected(folders, tmp_path, monkeypatch):
    source, target = folders
    selected_path = make_zip(source, entries={'a.pdf': b'a'})
    old_path = make_zip(source, TODAY - timedelta(days=100), entries={'old.pdf': b'o'})
    index = ZipService(cache_dir=tmp_path / 'cache')
    day = index.scan(source)[0]
    index.save()
    reopened = ZipService(cache_dir=tmp_path / 'cache')
    day = reopened.scan(source, 14, today=TODAY)[0]
    original, reads = zipfile.ZipFile, []
    def spy(path, *args, **kwargs):
        reads.append(Path(path))
        if Path(path) == old_path:
            raise AssertionError('Változatlan régi ZIP-et újraolvasott a fájlművelet')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(zipfile, 'ZipFile', spy)
    service = FileService(source, target, zip_service=reopened)
    service.extract(day)
    assert selected_path in reads
    service.delete(day, confirmed=True, expected_names={'a.pdf'})
    assert not (target / 'a.pdf').exists()


def test_common_directory_cannot_be_created_under_source_alias(folders, tmp_path):
    source, target = folders
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip('A tesztfiók nem hozhat létre mappahivatkozást')
    with pytest.raises(EDPDError):
        validate_shared_directory(alias / 'new-appdata', source, target)
    assert not (source / 'new-appdata').exists()


def test_transient_zip_read_error_is_retried_on_refresh_without_file_change(folders, tmp_path, monkeypatch):
    source, _ = folders
    path = make_zip(source)
    service = ZipService(cache_dir=tmp_path / 'cache')
    original, calls = zipfile.ZipFile, []
    def disconnected_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError('Átmeneti hálózati hiba')
        return original(*args, **kwargs)
    monkeypatch.setattr(zipfile, 'ZipFile', disconnected_once)
    first = service.scan(source, 14, today=TODAY)
    assert first[0].error
    stamp = path.stat().st_mtime_ns
    second = service.scan(source, 14, today=TODAY)
    assert not second[0].error and second[0].documents[0].name == 'a.pdf'
    assert path.stat().st_mtime_ns == stamp and len(calls) == 2


def test_local_index_never_writes_inside_source_archive(folders):
    source, _ = folders
    path = make_zip(source)
    index = ZipService(cache_dir=source / 'cache')
    assert index.scan(source, 14, today=TODAY)[0].documents
    index.save()
    assert list(source.iterdir()) == [path]


@pytest.mark.parametrize('operation', ['extract', 'mark'])
def test_detected_source_change_invalidates_index_even_with_preserved_stamp(folders, tmp_path, operation):
    source, target = folders
    path = make_zip(source, entries={'a.pdf': b'a'})
    index = ZipService(cache_dir=tmp_path / 'cache')
    old = index.scan(source)[0]
    stamp = path.stat()
    make_zip(source, entries={'a.pdf': b'b'})
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert path.stat().st_size == stamp.st_size
    with pytest.raises(EDPDError, match='megváltozott'):
        if operation == 'extract':
            FileService(source, target, zip_service=index).extract(old)
        else:
            CompletionStore(tmp_path / 'shared', source, target, zip_service=index).set_done(old, True)
    current = index.scan(source)[0]
    assert current.documents[0].crc != old.documents[0].crc
    FileService(source, target, zip_service=index).extract(current)
    assert (target / 'a.pdf').read_bytes() == b'b'
