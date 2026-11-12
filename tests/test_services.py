import hashlib
import multiprocessing
import os
import zipfile
from datetime import date
from pathlib import Path
import pytest
from edpd.config import Settings
from edpd.file_service import FileService, validate_paths
from edpd.locking import workspace_lock
from edpd.models import Capabilities, EDPDError
from edpd.pdf_service import PDFService
from edpd.print_service import print_pages
from edpd.state_service import inventory, day_status
from edpd.zip_service import ZipService, read_document


def archive(source, name='20261111_HIVATAL_1.zip', entries=None):
    path = source / name
    with zipfile.ZipFile(path, 'w') as z:
        for member, content in (entries or {'nested/árvíztűrő.pdf': b'first', 'osszesito.csv': b'ignore'}).items():
            z.writestr(member, content)
    return path


def selected(source):
    return ZipService().scan(source)[0]


def test_group_dates_csv_and_flat_names(folders):
    source, _ = folders
    archive(source)
    archive(source, '20261111_MAS_2.ZIP', {'más.pdf': b'2'})
    archive(source, '20261110_ELTERO.zip')
    archive(source, '20260230_invalid.zip')
    archive(source, 'random.zip')
    days = ZipService().scan(source)
    assert [d.date for d in days] == [date(2026, 11, 11), date(2026, 11, 10)]
    assert len(days[0].archives) == 2
    assert {d.name for d in days[0].documents} == {'árvíztűrő.pdf', 'más.pdf'}


def test_extract_skip_overwrite_and_source_unchanged(folders):
    source, target = folders
    path = archive(source)
    digest = hashlib.sha256(path.read_bytes()).digest()
    service, day = FileService(source, target), selected(source)
    assert '1 PDF' in service.extract(day)
    assert not list(target.glob('*.csv'))
    dest = target / 'árvíztűrő.pdf'
    dest.write_bytes(b'existing')
    service.extract(day, 'skip')
    assert dest.read_bytes() == b'existing'
    service.extract(day, 'overwrite')
    assert dest.read_bytes() == b'first'
    with pytest.raises(EDPDError):
        service.extract(day, 'cancel')
    assert hashlib.sha256(path.read_bytes()).digest() == digest
    assert sorted(p.name for p in source.iterdir()) == [path.name]


def test_actual_states(folders):
    source, target = folders
    archive(source, entries={'a.pdf': b'a', 'b.pdf': b'bb'})
    day = selected(source)
    assert day_status(day, inventory(target)) == 'Nincs kicsomagolva'
    (target / 'a.pdf').write_bytes(b'a')
    assert day_status(day, inventory(target)) == 'Részben kicsomagolva'
    (target / 'b.pdf').write_bytes(b'bb')
    assert day_status(day, inventory(target)) == 'Kicsomagolva'
    (target / 'b.pdf').write_bytes(b'different')
    assert day_status(day, inventory(target)) == 'Fájlütközés'


def test_daily_delete_and_clear_only_pdfs(folders):
    source, target = folders
    archive(source)
    day = selected(source)
    service = FileService(source, target)
    service.extract(day)
    (target / 'más.PDF').write_bytes(b'other')
    (target / 'keep.csv').write_text('keep')
    (target / 'sub').mkdir()
    with pytest.raises(EDPDError):
        service.delete(day, expected_names={'árvíztűrő.pdf'})
    service.delete(day, confirmed=True, expected_names={'árvíztűrő.pdf'})
    assert (target / 'más.PDF').exists()
    with pytest.raises(EDPDError, match='megváltozott'):
        service.delete(confirmed=True, expected_names=set())
    service.delete(confirmed=True, expected_names={'más.pdf'})
    assert (target / 'keep.csv').exists() and (target / 'sub').is_dir()
    assert not list(target.glob('*.PDF'))


def test_missing_and_nested_paths(folders):
    source, target = folders
    with pytest.raises(EDPDError, match='nem érhető el'):
        validate_paths(source, target / 'missing')
    for a, b in [(source, source), (source, source.parent), (source.parent, target)]:
        with pytest.raises(EDPDError):
            validate_paths(a, b)


@pytest.mark.parametrize('name', ['../escape.pdf', '/abs.pdf', 'C:\\evil.pdf', 'x/../../a.pdf', 'NUL.pdf', 'a:b.pdf', 'dir\\..\\bad.pdf'])
def test_unsafe_zip(folders, name):
    source, target = folders
    archive(source, entries={name: b'bad'})
    day = selected(source)
    assert day.error
    with pytest.raises(EDPDError):
        FileService(source, target).extract(day)
    assert not list(target.glob('*.pdf'))


def test_bad_zip_keeps_other_days(folders):
    source, _ = folders
    archive(source)
    (source / '20261112_bad.zip').write_bytes(b'broken')
    days = ZipService().scan(source)
    assert days[0].error and not days[1].error


def test_collisions_and_viewer_permissions(folders):
    source, target = folders
    archive(source, entries={'a.pdf': b'a', 'folder/A.pdf': b'b'})
    assert selected(source).error
    for path in source.iterdir():
        path.unlink()
    archive(source, entries={'a.pdf': b'a'})
    day = selected(source)
    limited = FileService(source, target, Capabilities(False, False))
    limited.extract(day)
    with pytest.raises(EDPDError):
        limited.extract(day, 'overwrite')
    with pytest.raises(EDPDError):
        limited.delete(day, confirmed=True, expected_names={'a.pdf'})
    archive(source, '20261110_2.zip', {'a.pdf': b'b'})
    with pytest.raises(EDPDError, match='Más napi'):
        FileService(source, target).extract(day)
    with pytest.raises(EDPDError, match='Több nap'):
        FileService(source, target).delete(day, confirmed=True, expected_names={'a.pdf'})


def test_changed_zip_refused(folders):
    source, target = folders
    archive(source)
    day = selected(source)
    archive(source, entries={'new.pdf': b'new'})
    with pytest.raises(EDPDError, match='megváltozott'):
        FileService(source, target).extract(day)


def hold_lock(target, ready, release):
    with workspace_lock(Path(target)):
        ready.set()
        release.wait(10)


def test_cross_process_lock_and_crash_recovery(folders):
    _, target = folders
    ctx = multiprocessing.get_context('spawn')
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=hold_lock, args=(str(target), ready, release))
    process.start()
    try:
        assert ready.wait(10)
        with pytest.raises(EDPDError):
            with workspace_lock(target):
                pytest.fail('Második folyamat megszerezte a zárat')
        process.terminate()
        process.join(10)
        with workspace_lock(target):
            pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)


def test_failed_replace_preserves_original_and_cleans_temp(folders, monkeypatch):
    source, target = folders
    archive(source)
    service, day = FileService(source, target), selected(source)
    service.extract(day)
    destination = target / 'árvíztűrő.pdf'
    destination.write_bytes(b'old')
    def fail(*args):
        raise OSError('Hálózati kapcsolat megszakadt')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        service.extract(day, 'overwrite')
    assert destination.read_bytes() == b'old'
    assert not list(target.glob('.edpd-*.tmp'))


def test_settings_roundtrip(tmp_path):
    path = tmp_path / 'local' / 'settings.json'
    settings = Settings(source='\\\\szerver\\megosztás', refresh_minutes=30)
    settings.save(path)
    assert Settings.load(path) == settings
    assert Settings.load(tmp_path / 'missing.json').refresh_minutes == 15
    path.write_text('{"refresh_minutes": 7}')
    with pytest.raises(ValueError):
        Settings.load(path)


def test_pdf_render_and_print_range(pdf_bytes):
    pdf = PDFService(pdf_bytes)
    assert pdf.pages == 3
    pix = pdf.render(0)
    assert pix.width > 500 and pix.height > 700
    assert pdf.render(0) is pix
    assert print_pages(pdf.pages, 2, 3) == [1, 2]
    assert print_pages(pdf.pages, reverse=True) == [2, 1, 0]
    pdf.close()
    with pytest.raises(EDPDError):
        PDFService(b'not a pdf')


def test_zip_read_no_extraction(folders, pdf_bytes):
    source, target = folders
    archive(source, entries={'folder/document.pdf': pdf_bytes})
    assert read_document(selected(source).documents[0]) == pdf_bytes
    assert not list(target.iterdir())


def test_print_full_pages_to_pdf(app, pdf_bytes, tmp_path):
    from PySide2.QtPrintSupport import QPrinter
    from edpd.print_service import render_to_printer
    import fitz as pymupdf
    output = tmp_path / 'printed.pdf'
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output))
    printer.setFromTo(2, 3)
    pdf = PDFService(pdf_bytes)
    render_to_printer(pdf, printer)
    pdf.close()
    with pymupdf.open(output) as printed:
        assert printed.page_count == 2
        # A teljes oldal képként került a nyomtatási kimenetre, nem a képernyő kivágása.
        assert printed[0].get_images()
        assert printed[1].get_pixmap().width > 500


def test_symlink_target_refused(folders):
    source, target = folders
    outside = target.parent / 'outside.pdf'
    outside.write_bytes(b'preserve')
    try:
        (target / 'a.pdf').symlink_to(outside)
    except OSError:
        pytest.skip('A tesztfiók nem hozhat létre szimbolikus linket')
    with pytest.raises(EDPDError):
        inventory(target)
    assert outside.read_bytes() == b'preserve'


def test_cache_refresh_when_zip_changes(folders):
    source, _ = folders
    archive(source)
    service = ZipService()
    first = service.scan(source)
    second = service.scan(source)
    assert first[0].documents[0] is second[0].documents[0]
    archive(source, entries={'new.pdf': b'longer content'})
    assert service.scan(source)[0].documents[0].name == 'new.pdf'


def test_partial_delete_failure_reported(folders, monkeypatch):
    source, target = folders
    archive(source, entries={'a.pdf': b'a', 'b.pdf': b'b'})
    service, day = FileService(source, target), selected(source)
    service.extract(day)
    original = Path.unlink
    def fail_one(self, *args, **kwargs):
        if self.name == 'b.pdf':
            raise PermissionError('Foglalt fájl')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_one)
    with pytest.raises(EDPDError, match='1 PDF törölve'):
        service.delete(day, confirmed=True, expected_names={'a.pdf', 'b.pdf'})
    assert not (target / 'a.pdf').exists()
    assert (target / 'b.pdf').exists()


def test_archive_paths_are_canonical_across_source_aliases(folders):
    source, target = folders
    archive(source)
    alias = source.parent / 'archive-alias'
    try:
        alias.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip('A tesztfiók nem hozhat létre mappahivatkozást')
    selected_day = selected(alias)
    assert selected_day == selected(source)
    assert selected_day.archives[0].parent == source.resolve()
    service = FileService(alias, target)
    service.extract(selected_day)
    assert (target / 'árvíztűrő.pdf').read_bytes() == b'first'
    service.delete(selected_day, confirmed=True, expected_names={'árvíztűrő.pdf'})
