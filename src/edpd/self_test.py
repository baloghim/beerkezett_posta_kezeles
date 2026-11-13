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
    from . import __version__, DISPLAY_NAME
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
        from PySide2.QtWidgets import QApplication, QMessageBox, QStyleFactory
        from PySide2.QtPrintSupport import QPrinter
        from .config import Settings
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
        historical_path = source / f'{date.today() - timedelta(days=1000):%Y%m%d}_HISTORICAL.zip'
        with zipfile.ZipFile(historical_path, 'w') as archive:
            archive.writestr('historical.pdf', data)
        (source / 'invalid_date.zip').write_bytes(b'not a valid ZIP')
        app = QApplication([])
        app.setApplicationDisplayName(DISPLAY_NAME)
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
                if window is not None and (window.access_error):
                    raise RuntimeError(window.access_error)
                if condition():
                    return
                time.sleep(0.01)
            raise TimeoutError('A felület háttérművelete nem fejeződött be.')
        try:
            window = MainWindow(Settings(source=str(source), target=str(target)))
            window.show()
            wait(lambda: bool(window.entries) and not window.jobs)
            if len(window.days) != 2 or len(window.days[0].documents) != 2:
                raise RuntimeError('Hibás napi csoportosítás.')
            if historical_path.resolve() in window.zip.cache:
                raise RuntimeError('Induláskor időszakon kívüli ZIP-et dolgozott fel.')
            result['startup_archives'] = {'total_valid_zips': len(window.entries), 'in_period_zips': sum(len(d.archives) for d in window.days),
                                          'upper_rows': window.day_table.rowCount(), 'historical_zip_opened': False}
            from .ui.appearance import apply_style
            result['qt_styles'] = []
            for style in QStyleFactory.keys():
                apply_style(style)
                app.processEvents()
                if app.style().objectName().lower() != style.lower() or app.styleSheet():
                    raise RuntimeError('A gyári Qt-stílus nem alkalmazható: ' + style)
                result['qt_styles'].append(style)
            apply_style(window.settings.qt_style)
            result['checks'].append('three_panel_gui_and_zip_scan')
            from .ui.about_dialog import AboutDialog
            about = AboutDialog(window)
            normal_pt = app.font().pointSizeF()
            main_pt = window.operation_toolbar.widgetForAction(window.actions[0]).font().pointSizeF()
            pdf_pt = window.viewer.toolbar.font().pointSizeF()
            if (window.windowTitle() != f'{DISPLAY_NAME} {__version__}' or
                    DISPLAY_NAME not in about.windowTitle() or DISPLAY_NAME not in about.info.toPlainText() or
                    normal_pt <= 0 or main_pt != normal_pt + 2 or pdf_pt != normal_pt):
                raise RuntimeError('Hibás programnév vagy eszköztár-betűméret.')
            result['branding'] = {'display_name': DISPLAY_NAME, 'window_title': window.windowTitle(),
                                  'about_title': about.windowTitle(), 'normal_font_pt': normal_pt,
                                  'main_toolbar_font_pt': main_pt, 'pdf_toolbar_font_pt': pdf_pt}
            about.reject()
            result['checks'].append('display_name_and_main_toolbar_font')
            headers = [window.docs_table.horizontalHeaderItem(i).text() for i in range(window.docs_table.columnCount())]
            if headers != ['Dátum', 'Fájlnév', 'Méret'] or window.workspace_panel.title_label.text() != 'A munkamappa dokumentumai':
                raise RuntimeError('A becsomagolt felület munkamappa-táblája hibás.')
            for row in range(window.day_table.rowCount()):
                window.day_table.selectRow(row)
                if window.docs_table.rowCount() != 0:
                    raise RuntimeError('Az üres munkamappában ZIP-beli fájlokat listázott a felület.')
            (target / 'workspace_only.pdf').write_bytes(data)
            window.refresh()
            wait(lambda: not window.jobs)
            if window.docs_table.rowCount() != 1 or window.docs_table.item(0, 1).text() != 'workspace_only.pdf':
                raise RuntimeError('Az alsó tábla nem a tényleges munkamappát mutatja.')
            result['ui_contract'] = {'window_title': window.windowTitle(), 'workspace_title': window.workspace_panel.title_label.text(),
                                     'workspace_headers': headers, 'history_days': window.settings.history_days,
                                     'workspace_files_after_upper_selection': [window.docs_table.item(i, 1).text() for i in range(window.docs_table.rowCount())]}
            if window.origin_requested or window.origin_timer.isActive():
                raise RuntimeError('Automatikus történeti forráskeresés indult.')
            (target / 'workspace_only.pdf').unlink()
            window.refresh()
            wait(lambda: not window.jobs)
            window.day_table.selectRow(0)
            result['checks'].append('independent_workspace_table_and_source_day_column')
            window.open_archive_document(window.days[0].documents[0])
            wait(lambda: window.viewer.pdf is not None and not window.jobs)
            if window.viewer.fit_mode != 'width':
                raise RuntimeError('Az új PDF nem Szélesség nézetben nyílt meg.')
            window.viewer.page_action.trigger()
            if window.viewer.fit_mode != 'page':
                raise RuntimeError('A Teljes oldal nézet nem aktiválható.')
            window.viewer.move(2)
            window.viewer.zoom(1.25)
            window.viewer.fit('width')
            if window.viewer.pdf.pages != 3 or window.viewer.label.pixmap().isNull() or list(target.iterdir()):
                raise RuntimeError('Hibás ZIP-betekintés vagy PDF-renderelés.')
            app.processEvents()
            # Measure visible controls, not coordinates of overflow-menu widgets.
            toolbar = window.viewer.toolbar
            toolbar_width = sum(toolbar.widgetForAction(action).sizeHint().width()
                                for action in toolbar.actions()) + 128
            toolbar.setMinimumWidth(toolbar_width)
            window.setMinimumWidth(toolbar_width + window.left.minimumSizeHint().width() + 128)
            app.processEvents()
            from PySide2.QtCore import QEventLoop, QTimer
            settle = QEventLoop()
            QTimer.singleShot(30, settle.quit)
            settle.exec_()
            buttons = [window.viewer.toolbar.widgetForAction(action) for action in
                       (window.viewer.width_action, window.viewer.page_action,
                        window.viewer.print_action, window.viewer.save_action)]
            fit_gap = buttons[1].geometry().left() - buttons[0].geometry().right() - 1
            save_gap = buttons[3].geometry().left() - buttons[2].geometry().right() - 1
            result['pdf_toolbar'] = {'fit_gap_px': fit_gap, 'print_save_gap_px': save_gap,
                                     'toolbar_width_px': toolbar.width(),
                                     'buttons_visible': [button.isVisible() for button in buttons]}
            if fit_gap < 6 or fit_gap != save_gap or not all(button.isVisible() for button in buttons):
                raise RuntimeError('Nem egységes a PDF-eszköztár térköze.')
            result['checks'].append('pdf_fit_toolbar_spacing')
            result['checks'].append('zip_pdf_preview_paging_zoom')
            viewer = window.viewer
            viewer.move(1)
            viewer.zoom(2.0 / viewer.scale)
            zoom_scale = viewer.scale
            app.processEvents()
            navigation = {action.property('icon_role'): action for action in viewer.toolbar.actions() if action.text()}
            result['pdf_navigation'] = []
            for role, expected_page in [('next', 2), ('previous', 1), ('first', 0), ('last', 2)]:
                bars = viewer.scroll.horizontalScrollBar(), viewer.scroll.verticalScrollBar()
                for bar in bars:
                    bar.setValue(bar.maximum())
                if not all(bar.value() > 0 for bar in bars):
                    raise RuntimeError('A lapozási próba nem görgetett PDF-et.')
                navigation[role].trigger()
                app.processEvents()
                if viewer.page != expected_page or any(bar.value() != 0 for bar in bars):
                    raise RuntimeError('Lapozáskor nem a PDF teteje/bal széle jelenik meg.')
                if viewer.scale != zoom_scale or viewer.fit_mode is not None:
                    raise RuntimeError('Lapozáskor elveszett a nagyítás vagy a nézetmód.')
                result['pdf_navigation'].append({'action': role, 'page': viewer.page,
                                                  'horizontal': bars[0].value(), 'vertical': bars[1].value(),
                                                  'scale': viewer.scale, 'fit_mode': viewer.fit_mode})
            viewer.fit('width')
            result['checks'].append('pdf_paging_resets_scroll_preserves_zoom')
            with workspace_lock(target):
                try:
                    with workspace_lock(target):
                        raise RuntimeError('A második zárolás váratlanul sikerült.')
                except EDPDError:
                    pass
            result['checks'].append('workspace_file_lock')
            day = window.days[0]
            service = FileService(source, target)
            window.extract()
            if not window.extracting or not window.extraction_bar.isVisible():
                raise RuntimeError('A kicsomagolás folyamatjelzője nem jelent meg.')
            wait(lambda: not window.extracting and not window.jobs)
            if window.extraction_bar.isVisible() or list(target.glob('*.csv')):
                raise RuntimeError('Hibás kicsomagolási befejezés.')
            if window.day_table.item(0, 3).text() != 'Kicsomagolva':
                raise RuntimeError('Hibás kicsomagolási állapot.')
            # A munkamappából megnyitás is az éles UI-kódon keresztül fut.
            window.docs_table.selectRow(0)
            wait(lambda: not window.jobs)
            result['checks'].append('extract_and_workspace_preview')
            from .pdf_export import save_pdf
            exported = base / 'exported.pdf'
            save_pdf(window.viewer.pdf.data, exported, source, target)
            if exported.read_bytes() != data or window.viewer.filename not in ('a.pdf', 'b.pdf'):
                raise RuntimeError('Az eredeti PDF-bájtok mentése hibás.')
            result['checks'].append('pdf_export_original_bytes')
            from .processed_store import ProcessedStore, packet_id
            window.mark_day(day)
            wait(lambda: not window.jobs)
            if packet_id(source, day) not in ProcessedStore(source, target).read() or not window.day_table.item(0, 3).text().startswith('Feldolgozva'):
                raise RuntimeError('A helyi feldolgozási jelölés nem maradt meg.')
            result['checks'].append('local_processed_marks')
            import threading
            cancel = threading.Event()
            before = {p.name: p.read_bytes() for p in target.glob('*.pdf')}
            def cancelled(text, done, total):
                if text == 'PDF-ek véglegesítése' and done == 1:
                    cancel.set()
            service.extract(day, 'overwrite', expected_existing=service.extraction_plan(day).existing, progress=cancelled, cancel=cancel)
            if before != {p.name: p.read_bytes() for p in target.glob('*.pdf')} or list(target.glob('.edpd-recovery-*')):
                raise RuntimeError('A megszakított tranzakció visszavonása hibás.')
            result['checks'].append('transaction_cancel_rollback')
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
            from .ui.icons import icon, ASSETS
            metadata = json.loads((ASSETS / 'manifest.json').read_text())
            result['icons'] = list(metadata['icons']) + ['app']
            for name in result['icons']:
                if icon(name).pixmap(32, 32).isNull():
                    raise RuntimeError('Hiányzó Crystal ikon: ' + name)
            if window.windowIcon().isNull() or not (ASSETS / 'edpd.ico').is_file():
                raise RuntimeError('Hiányzó EDPD alkalmazásikon.')
            result['checks'].append('crystal_icons_and_application_icon')
            from .ui.icons import THEME_NAMES, set_theme
            result['icon_themes'] = []
            for theme in THEME_NAMES:
                set_theme(theme)
                app.processEvents()
                for role in metadata['icons']:
                    if icon(role).pixmap(22, 22).isNull():
                        raise RuntimeError('Hiányzó témaikon: ' + theme + ' / ' + role)
                if window.actions[0].icon().cacheKey() != icon('extract').cacheKey():
                    raise RuntimeError('A fő eszköztár ikonja nem frissült.')
                if window.viewer.print_action.icon().cacheKey() != icon('print').cacheKey():
                    raise RuntimeError('A PDF eszköztár ikonja nem frissült.')
                result['icon_themes'].append(theme)
            set_theme(window.settings.icon_theme)
            result['checks'].append('five_live_icon_themes')
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
