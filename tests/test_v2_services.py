import json
import multiprocessing
import os
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from edpd.config import Settings
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
    assert complete and labels['a.pdf'] == 'Több lehetséges nap'
    make_zip(source, old, entries={'different.pdf': b'longer'})
    entries = service.catalogue(source)
    labels, pending, complete = service.origin_state(source, files, entries)
    assert not complete and pending and labels['a.pdf'] == TODAY.strftime('%Y.%m.%d.')
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
    settings = Settings(source=value, history_days=90)
    path = tmp_path / 'settings.json'
    settings.save(path)
    loaded = Settings.load(path)
    assert loaded.source == expected and loaded.history_days == 90


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


def test_daily_deletion_exact_subset_preserves_other_days(folders, tmp_path):
    source, target = folders
    make_zip(source, entries={f'a{i}.pdf': str(i).encode() for i in range(6)})
    make_zip(source, TODAY - timedelta(days=100), entries={'other.pdf': b'o'})
    day = ZipService().scan(source, 14, today=TODAY)[0]
    for index in range(4):
        (target / f'a{index}.pdf').write_bytes(str(index).encode())
    (target / 'other.pdf').write_bytes(b'o')
    (target / 'keep.csv').write_text('keep')
    service = FileService(source, target)
    names = service.deletion_plan(day)
    assert names == {f'a{i}.pdf' for i in range(4)}
    service.delete(day, confirmed=True, expected_names=names)
    assert (target / 'other.pdf').read_bytes() == b'o'
    assert (target / 'keep.csv').exists()
    assert not list(target.glob('a*.pdf'))


def test_hidden_old_archive_collision_blocks_daily_deletion(folders):
    source, target = folders
    make_zip(source, entries={'shared.pdf': b'a'})
    make_zip(source, TODAY - timedelta(days=200), entries={'shared.pdf': b'a'})
    day = ZipService().scan(source, 14, today=TODAY)[0]
    (target / 'shared.pdf').write_bytes(b'a')
    with pytest.raises(EDPDError, match='Több nap'):
        FileService(source, target).deletion_plan(day)
    assert (target / 'shared.pdf').exists()


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


def test_detected_source_change_invalidates_index_even_with_preserved_stamp(folders, tmp_path):
    source, target = folders
    path = make_zip(source, entries={'a.pdf': b'a'})
    index = ZipService(cache_dir=tmp_path / 'cache')
    old = index.scan(source)[0]
    stamp = path.stat()
    make_zip(source, entries={'a.pdf': b'b'})
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert path.stat().st_size == stamp.st_size
    with pytest.raises(EDPDError, match='megváltozott'):
        FileService(source, target, zip_service=index).extract(old)
    current = index.scan(source)[0]
    assert current.documents[0].crc != old.documents[0].crc
    FileService(source, target, zip_service=index).extract(current)
    assert (target / 'a.pdf').read_bytes() == b'b'
