"""Kiadást blokkoló, tényleges Qt-táblázatos regressziók."""
import json
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from PySide2.QtCore import Qt
from PySide2.QtTest import QTest
from PySide2.QtWidgets import QDialog, QMessageBox
from edpd.config import Settings
from edpd.ui.main_window import MainWindow
import edpd.ui.main_window as ui_module

TODAY = date(2026, 11, 12)


def wait(app, condition, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError('A grafikus állapot nem készült el')


def idle(app, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)


def make_zip(source, when, names):
    path = source / f'{when:%Y%m%d}_HIVATAL.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name in names:
            archive.writestr(name, b'%PDF metadata test')
    return path


@pytest.fixture(scope='module')
def thousand_archives(tmp_path_factory):
    source = tmp_path_factory.mktemp('thousand_archives')
    paths = {}
    for offset in range(1000):
        day = TODAY - timedelta(days=offset)
        paths[make_zip(source, day, [f'doc_{offset}.pdf'])] = day
    assert len({d.year for d in paths.values()}) >= 3
    return source, paths


@pytest.mark.parametrize('period', [14, 30, 90, 180, None])
def test_thousand_archives_actual_qt_rows_and_all_zip_opens(app, thousand_archives, tmp_path, monkeypatch, record_property, pdf_bytes, period):
    source, paths = thousand_archives
    target = tmp_path / 'workspace'
    target.mkdir()
    # Nem üres cél: ezzel a régi rejtett automatikus forráskeresés is lebukik.
    (target / 'unknown.pdf').write_bytes(pdf_bytes)
    expected = set(paths) if period is None else {p for p, d in paths.items() if 0 <= (TODAY - d).days < period}
    original, opened, errors = zipfile.ZipFile, [], []
    def spy(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            actual = Path(path).resolve()
            if actual in paths:
                opened.append(actual)
        return original(path, *args, **kwargs)
    def reject_content_read(*args, **kwargs):
        raise AssertionError('Induláskor/listázáskor PDF-tartalmat olvasott')
    monkeypatch.setattr(original, 'read', reject_content_read)
    monkeypatch.setattr(zipfile, 'ZipFile', spy)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    settings = Settings(source=str(source), target=str(target), history_days=period)
    window = MainWindow(settings, today_provider=lambda: TODAY)
    window.show()
    try:
        wait(app, lambda: window.day_table.rowCount() == len(expected) and not window.jobs)
        # Több régi origin_timer ciklusnak is volna ideje lefutni.
        idle(app, 0.85)
        assert not window.origin_requested and not window.origin_timer.isActive()
        assert set(opened) == expected
        assert len(opened) == len(expected)
        expected_dates = sorted((paths[p] for p in expected), reverse=True)
        actual_dates = [window.day_table.item(row, 0).text() for row in range(window.day_table.rowCount())]
        assert actual_dates == [d.strftime('%Y.%m.%d.') for d in expected_dates]
        assert window.docs_table.rowCount() == 1
        assert window.docs_table.item(0, 1).text() == 'unknown.pdf'
        assert [window.docs_table.horizontalHeaderItem(i).text() for i in range(3)] == ['Dátum', 'Fájlnév', 'Méret']
        assert window.docs_table.item(0, 0).text() == 'Ismeretlen'
        for row in (0, len(expected) - 1):
            window.day_table.selectRow(row)
        # Az automatikus frissítés is csak a beállított időszakot érintheti.
        window.timer.timeout.emit()
        wait(app, lambda: not window.jobs)
        idle(app, 0.35)
        assert set(opened) == expected and len(opened) == len(expected)
        assert not errors
        for key, value in {'total_zip_count': len(list(source.glob('*.zip'))), 'period': period or 'all',
                           'in_period_zip_count': len(expected), 'actual_zip_opens': len(opened),
                           'upper_table_rows': window.day_table.rowCount(), 'out_of_period_zip_opens': sum(p not in expected for p in opened)}.items():
            record_property(key, value)
    finally:
        window.origin_requested = False
        window.origin_timer.stop()
        window.files.clear()
        wait(app, lambda: not window.jobs)
        window.close()


def table_files(window):
    return {window.docs_table.item(i, 1).text() for i in range(window.docs_table.rowCount())}


def test_three_days_workspace_model_and_real_ui_mutations(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    first_names = {f'd09_{i}.pdf' for i in range(6)}
    second_names = {f'd10_{i}.pdf' for i in range(6)}
    make_zip(source, TODAY - timedelta(days=3), first_names)
    make_zip(source, TODAY - timedelta(days=2), second_names)
    make_zip(source, TODAY - timedelta(days=1), {'d11.pdf'})
    for name in first_names:
        (target / name).write_bytes(pdf_bytes)
    (target / 'keep.csv').write_text('keep')
    (target / 'subfolder').mkdir()
    before_source = {p.name: p.read_bytes() for p in source.iterdir()}
    original_inventory, inventory_calls, errors, dialogs = ui_module.inventory, [], [], []
    def inventory_spy(path):
        inventory_calls.append(Path(path))
        return original_inventory(path)
    monkeypatch.setattr(ui_module, 'inventory', inventory_spy)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'exec_', lambda self: 0)
    monkeypatch.setattr(QMessageBox, 'clickedButton', lambda self: next(b for b in self.buttons() if b.text() == 'Meglévők kihagyása, hiányzók kicsomagolása'))
    monkeypatch.setattr(QDialog, 'exec_', lambda self: dialogs.append(self.windowTitle()) or 0)
    settings = Settings(source=str(source), target=str(target))
    window = MainWindow(settings, today_provider=lambda: TODAY)
    window.show()
    try:
        wait(app, lambda: len(window.days) == 3 and not window.jobs)
        assert table_files(window) == first_names
        model = window.workspace_model
        reads_before = len(inventory_calls)
        for row in (2, 1, 0):
            window.day_table.selectRow(row)
            assert table_files(window) == first_names
            assert window.workspace_model is model
        window.day_table.selectRow(1)
        second_day = window.current_day()
        window.actions[0].trigger()
        wait(app, lambda: table_files(window) == first_names | second_names and not window.jobs)
        assert all(window.docs_table.item(i, 0).text() in ('2026.11.09.', '2026.11.10.') for i in range(12))
        window.actions[1].trigger()
        wait(app, lambda: table_files(window) == first_names and not window.jobs)
        window.actions[2].trigger()
        wait(app, lambda: window.docs_table.rowCount() == 0 and not window.jobs)
        assert (target / 'keep.csv').exists() and (target / 'subfolder').is_dir()
        assert before_source == {p.name: p.read_bytes() for p in source.iterdir()}
        assert not errors
    finally:
        window.close()


def test_old_origins_only_after_user_click_unknown_still_opens(app, folders, tmp_path, monkeypatch, pdf_bytes):
    source, target = folders
    recent = make_zip(source, TODAY, {'recent.pdf'})
    old = make_zip(source, TODAY - timedelta(days=100), {'old.pdf'})
    (target / 'old.pdf').write_bytes(pdf_bytes)
    original, opened, errors = zipfile.ZipFile, [], []
    def spy(path, *args, **kwargs):
        opened.append(Path(path).resolve())
        return original(path, *args, **kwargs)
    monkeypatch.setattr(zipfile, 'ZipFile', spy)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    window = MainWindow(Settings(source=str(source), target=str(target)), today_provider=lambda: TODAY)
    window.show()
    try:
        wait(app, lambda: bool(window.days) and not window.jobs)
        idle(app, 0.65)
        assert opened == [recent] and window.docs_table.item(0, 0).text() == 'Ismeretlen'
        window.docs_table.selectRow(0)
        wait(app, lambda: window.viewer.pdf is not None and not window.jobs)
        assert window.viewer.pdf.pages == 3 and opened == [recent]
        window.origin_button.click()
        wait(app, lambda: not window.origin_pending and not window.jobs)
        assert opened == [recent, old]
        assert window.docs_table.item(0, 0).text() == '2026.08.04.'
        assert not errors
    finally:
        window.close()


def test_cached_old_and_ambiguous_origins_in_actual_workspace_table(app, folders, tmp_path, monkeypatch, pdf_bytes):
    from edpd.config import cache_directory
    from edpd.zip_service import ZipService
    source, target = folders
    make_zip(source, TODAY, {'recent.pdf'})
    make_zip(source, TODAY - timedelta(days=1), {'both.pdf'})
    make_zip(source, TODAY - timedelta(days=100), {'old.pdf', 'both.pdf'})
    cached = ZipService(cache_dir=cache_directory())
    cached.scan(source)
    cached.save()
    for name in ['old.pdf', 'both.pdf', 'unknown.pdf']:
        (target / name).write_bytes(pdf_bytes)
    original, opened, errors = zipfile.ZipFile, [], []
    def spy(path, *args, **kwargs):
        opened.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(zipfile, 'ZipFile', spy)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    window = MainWindow(Settings(source=str(source), target=str(target)), today_provider=lambda: TODAY)
    window.show()
    try:
        wait(app, lambda: window.docs_table.rowCount() == 3 and not window.jobs)
        assert len(window.days) == 2 and table_files(window) == {'old.pdf', 'both.pdf', 'unknown.pdf'}
        values = {window.docs_table.item(i, 1).text(): window.docs_table.item(i, 0).text() for i in range(3)}
        assert values == {'old.pdf': '2026.08.04.', 'both.pdf': 'Több lehetséges nap', 'unknown.pdf': 'Ismeretlen'}
        assert opened == []
        window.docs_table.selectRow(window.work_keys.index('unknown.pdf'))
        wait(app, lambda: window.viewer.pdf is not None and not window.jobs)
        window.viewer.move(2)
        window.viewer.zoom(1.2)
        assert window.viewer.page == 2 and not opened and not errors
    finally:
        window.close()


def test_source_column_stays_visible_with_long_filename(app, folders, tmp_path, pdf_bytes):
    source, target = folders
    name = 'nagyon_hosszu_pdf_fajlnev_' * 2 + 'abcdef0123456789.pdf'
    make_zip(source, TODAY, {name})
    (target / name).write_bytes(pdf_bytes)
    window = MainWindow(Settings(source=str(source), target=str(target)), today_provider=lambda: TODAY)
    window.show()
    try:
        wait(app, lambda: window.docs_table.rowCount() == 1 and not window.jobs)
        app.processEvents()
        assert window.docs_table.horizontalHeaderItem(0).text() == 'Dátum'
        assert not window.docs_table.isColumnHidden(0)
        assert window.docs_table.columnViewportPosition(0) + window.docs_table.columnWidth(0) <= window.docs_table.viewport().width()
        assert window.docs_table.item(0, 1).toolTip() == name
    finally:
        window.close()
