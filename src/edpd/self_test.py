"""A kiadott EXE izolált ellenőrzése, Python/fejlesztőeszköz telepítése nélkül."""
import json
import os
import platform
import struct
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import date, timedelta
from pathlib import Path


def host_info():
    info = {'system': platform.system(), 'python': platform.python_version(),
            'bits': struct.calcsize('P') * 8, 'frozen': bool(getattr(sys, 'frozen', False))}
    if sys.platform == 'win32':
        version = sys.getwindowsversion()
        info.update(windows_major=version.major, build=version.build, product_type=version.product_type)
    return info


def run(report_path, require_windows1607=False):
    result = {'schema': 1, 'host': host_info(), 'passed': False, 'checks': [],
              'windows1607_verified': False, 'error': None}
    from . import __version__
    result['application_version'] = __version__
    report = Path(report_path).absolute()
    root = None
    app = None
    window = None
    previous_profile = os.environ.get('APPDATA')
    previous_local = os.environ.get('LOCALAPPDATA')
    try:
        is1607 = (result['host'].get('windows_major') == 10 and result['host'].get('build') == 14393
                  and result['host'].get('product_type') == 1 and result['host']['bits'] == 64)
        if require_windows1607 and not is1607:
            raise RuntimeError('A valódi Windows 10 1607 x64 (14393, munkaállomás) rendszer szükséges. Ez a gép nem az.')
        # Natív importok is a try blokkban: DLL-hiba esetén is marad diagnosztika.
        import fitz
        import PySide2
        from PySide2.QtCore import qVersion
        from PySide2.QtWidgets import QApplication, QMessageBox
        from PySide2.QtPrintSupport import QPrinter
        from .config import Settings
        from .completion_service import CompletionStore, day_identity
        from .file_service import FileService
        from .locking import workspace_lock
        from .models import EDPDError
        from .print_service import render_to_printer
        from .pdf_service import PDFService
        from .ui.main_window import MainWindow
        result['versions'] = {'PySide2': PySide2.__version__, 'Qt': qVersion(), 'PyMuPDF': fitz.VersionBind}
        result['checks'].append('native_imports')
        root = tempfile.TemporaryDirectory(prefix='EDPD-self-test-')
        base = Path(root.name)
        source, target = base / 'archive', base / 'workspace'
        source.mkdir()
        target.mkdir()
        os.environ['APPDATA'] = str(base / 'profile')
        os.environ['LOCALAPPDATA'] = str(base / 'local-profile')
        document = fitz.open()
        for index in range(3):
            page = document.new_page()
            page.insert_text((50, 75), f'EDPD synthetic test page {index + 1}')
        data = document.tobytes()
        document.close()
        for name, member in [(f'{date.today():%Y%m%d}_A.zip', 'nested/a.pdf'), (f'{date.today():%Y%m%d}_B.zip', 'b.pdf'), (f'{date.today() - timedelta(days=1):%Y%m%d}_C.zip', 'c.pdf')]:
            with zipfile.ZipFile(source / name, 'w') as archive:
                archive.writestr(member, data)
                archive.writestr('summary.csv', 'ignored')
        app = QApplication([])
        app.setStyle('Fusion')
        errors = []
        original_warning = QMessageBox.warning
        QMessageBox.warning = lambda *args: errors.append(str(args[-1]))
        def wait(condition):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                app.processEvents()
                if errors:
                    raise RuntimeError('\n'.join(errors))
                if window is not None and (window.access_error or window.shared_error):
                    raise RuntimeError(window.access_error or window.shared_error)
                if condition():
                    return
                time.sleep(0.01)
            raise TimeoutError('A felület háttérművelete nem fejeződött be.')
        try:
            window = MainWindow(Settings(source=str(source), target=str(target), shared_data=str(base / 'shared')))
            window.show()
            wait(lambda: len(window.days) == 2 and not window.jobs)
            if len(window.days[0].documents) != 2:
                raise RuntimeError('Hibás napi csoportosítás.')
            result['checks'].append('three_panel_gui_and_zip_scan')
            window.open_archive_document(window.days[0].documents[0])
            wait(lambda: window.viewer.pdf is not None and not window.jobs)
            window.viewer.move(2)
            window.viewer.zoom(1.25)
            window.viewer.fit('width')
            if window.viewer.pdf.pages != 3 or window.viewer.label.pixmap().isNull() or list(target.iterdir()):
                raise RuntimeError('Hibás ZIP-betekintés vagy PDF-renderelés.')
            result['checks'].append('zip_pdf_preview_paging_zoom')
            with workspace_lock(target):
                try:
                    with workspace_lock(target):
                        raise RuntimeError('A második zárolás váratlanul sikerült.')
                except EDPDError:
                    pass
            result['checks'].append('workspace_file_lock')
            day = window.days[0]
            service = FileService(source, target)
            service.extract(day)
            window.refresh()
            wait(lambda: not window.jobs)
            if window.day_table.item(0, 3).text() != 'Kicsomagolva':
                raise RuntimeError('Hibás kicsomagolási állapot.')
            # A munkamappából megnyitás is az éles UI-kódon keresztül fut.
            window.docs_table.selectRow(0)
            wait(lambda: not window.jobs)
            result['checks'].append('extract_and_workspace_preview')
            pdf = PDFService(data)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            output = base / 'printed.pdf'
            printer.setOutputFileName(str(output))
            printer.setFromTo(2, 3)
            render_to_printer(pdf, printer)
            pdf.close()
            with fitz.open(output) as printed:
                if printed.page_count != 2 or not printed[0].get_images():
                    raise RuntimeError('Hibás nyomtatási PDF-kimenet.')
            result['checks'].append('print_full_pages_to_pdf')
            service.delete(day, confirmed=True, expected_names={'a.pdf', 'b.pdf'})
            (target / 'other.pdf').write_bytes(data)
            (target / 'keep.csv').write_text('keep', encoding='utf-8')
            service.delete(confirmed=True, expected_names={'other.pdf'})
            if not (target / 'keep.csv').exists() or list(target.glob('*.pdf')):
                raise RuntimeError('Hibás törlési határok.')
            result['checks'].append('daily_delete_and_clear')
            store = CompletionStore(base / 'shared', source, target)
            store.set_done(day, True)
            if day_identity(day) not in store.read():
                raise RuntimeError('A közös Elvégezve jelölés nem maradt meg.')
            store.set_done(day, False)
            if day_identity(day) in store.read():
                raise RuntimeError('A jelölés visszavonása sikertelen.')
            result['checks'].append('shared_completion_mark_and_revoke')
            window.close()
            window = None
            restored = Settings.load(base / 'profile' / 'EDPD' / 'settings.json')
            if restored.source != str(source) or not restored.panels:
                raise RuntimeError('A helyi beállítások nem maradtak meg.')
            result['checks'].append('settings_and_layout_persistence')
        finally:
            QMessageBox.warning = original_warning
        result['passed'] = True
        result['windows1607_verified'] = is1607
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        # A JSON csak szintetikus tesztutakat és műszaki állapotot tartalmaz.
        if window is not None and not window.jobs:
            window.close()
        if previous_profile is None:
            os.environ.pop('APPDATA', None)
        else:
            os.environ['APPDATA'] = previous_profile
        if previous_local is None:
            os.environ.pop('LOCALAPPDATA', None)
        else:
            os.environ['LOCALAPPDATA'] = previous_local
        if root is not None:
            try:
                root.cleanup()
            except OSError as exc:
                result['passed'] = False
                result['error'] = (result['error'] or '') + f'\nTesztmappa-takarítási hiba: {exc}'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['passed'] else 1
