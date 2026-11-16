"""Packaged archive-browser functional checks, using synthetic data only."""
import json
import os
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from datetime import date, timedelta
from . import __version__


def run(report_path, require_windows1607=False, surface_theme='Alapértelmezett'):
    from .self_test import host_info
    result = {'passed': False, 'application_version': __version__, 'application': 'EDPD Betekintő',
              'host': host_info(), 'checks': [], 'error': None, 'windows1607_verified': False}
    report = Path(report_path).absolute()
    window = None
    previous = {k: os.environ.get(k) for k in ('APPDATA', 'LOCALAPPDATA')}
    try:
        is1607 = (result['host'].get('windows_major') == 10 and result['host'].get('build') == 14393
                  and result['host'].get('product_type') == 1 and result['host']['bits'] == 64)
        if require_windows1607 and not is1607:
            raise RuntimeError('Valódi Windows 10 1607 x64 szükséges.')
        import fitz
        import PySide2
        from PySide2.QtCore import qVersion
        from PySide2.QtWidgets import QApplication, QStyleFactory
        from PySide2.QtPrintSupport import QPrinter
        from .config import ViewerSettings, viewer_settings_path, viewer_cache_directory, Settings, settings_path
        from .ui.viewer_window import ViewerWindow, document_key
        from .ui.settings_dialog import SettingsDialog
        from .ui.appearance import apply_style
        from .ui.icons import THEME_NAMES, set_theme
        from .ui.themes import THEME_NAMES as SURFACES
        from .ui.themes import manager as surface_manager
        from .ui.appearance import apply_settings_style
        from .pdf_export import save_pdf
        from .print_service import render_to_printer
        from .single_instance import InstanceGuard
        result['versions'] = {'PySide2': PySide2.__version__, 'Qt': qVersion(), 'PyMuPDF': fitz.VersionBind}
        result['checks'].append('native_imports')
        app = QApplication.instance() or QApplication([])
        app.setApplicationDisplayName('EDPD Betekintő')
        with tempfile.TemporaryDirectory(prefix='EDPD-viewer-selftest-') as tmp:
            base = Path(tmp)
            os.environ['APPDATA'], os.environ['LOCALAPPDATA'] = str(base/'profile'), str(base/'local')
            source = base/'archive'; source.mkdir()
            pdf = fitz.open()
            for n in range(3):
                page = pdf.new_page(); page.insert_text((50, 75), f'Synthetic viewer page {n}')
            data = pdf.tobytes(); pdf.close()
            archives = []
            for suffix in ('A', 'B'):
                path = source/f'{date.today():%Y%m%d}_{suffix}.zip'
                with zipfile.ZipFile(path, 'w') as z:
                    z.writestr('same.pdf', data)
                archives.append(path)
            empty = source/f'{date.today()-timedelta(days=1):%Y%m%d}_EMPTY.zip'
            with zipfile.ZipFile(empty, 'w'): pass
            original = {p.name: p.read_bytes() for p in source.iterdir()}
            Settings(source=str(source), target=str(base/'DO-NOT-USE')).save()
            manager_bytes = settings_path().read_bytes()
            settings = ViewerSettings(source=str(source), surface_theme=surface_theme, ui_style=surface_theme if surface_theme != 'Alapértelmezett' else 'Fusion')
            settings.save()
            assert not hasattr(ViewerSettings.load(), 'target')
            assert 'target' not in json.loads(viewer_settings_path().read_text())
            assert 'EDPD-Betekinto' in str(viewer_cache_directory())
            result['checks'].append('separate_configuration_no_workspace_field')
            window = ViewerWindow(settings)
            window.show()
            def wait(condition):
                deadline = time.monotonic()+30
                while time.monotonic()<deadline:
                    app.processEvents()
                    if condition(): return
                    time.sleep(.01)
                raise AssertionError('Viewer readiness timeout: '+window.access_notice.text())
            wait(lambda: len(window.days)==2 and not window.jobs)
            assert not window.access_notice.text(), window.access_notice.text()
            assert [a.text() for a in window.main_toolbar.actions()]==['Frissítés','Beállítások']
            assert window.day_table.columnCount()==3
            assert window.day_table.contextMenuPolicy()!=__import__('PySide2.QtCore',fromlist=['Qt']).Qt.CustomContextMenu
            result['checks'].append('archive_only_toolbar_columns_no_context_menu')
            assert window.current_day().date==date.today() and len(window.documents)==2
            assert len({document_key(d) for d in window.documents})==2
            assert [d.archive.name for d in window.documents]==sorted(p.name for p in archives)
            result['checks'].append('newest_day_multi_zip_duplicate_names')
            window.docs_table.setCurrentCell(0,0)
            wait(lambda: window.viewer.pdf is not None and not window.jobs)
            assert window.viewer.pdf.data==data
            result['checks'].append('direct_zip_memory_preview')
            window.viewer.move(2); window.viewer.zoom(1.25)
            assert window.viewer.page==2 and window.viewer.fit_mode is None
            window.viewer.fit('width'); window.viewer.fit('page')
            result['checks'].append('pdf_navigation_zoom_fit')
            export=base/'export.pdf';save_pdf(window.viewer.pdf.data,export,source)
            assert export.read_bytes()==data
            result['checks'].append('exact_pdf_export')
            printer=QPrinter(QPrinter.HighResolution);printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(str(base/'print.pdf'));render_to_printer(window.viewer.pdf,printer)
            with fitz.open(base/'print.pdf') as printed: assert len(printed)==3
            result['checks'].append('print_all_pages_to_pdf')
            selected=window.viewer.pdf
            window.refresh(); wait(lambda:not window.jobs)
            assert window.viewer.pdf is selected and window.current_document() is not None
            result['checks'].append('refresh_preserves_unchanged_preview')
            window.day_table.setCurrentCell(1,0)
            assert not window.documents and window.viewer.pdf is None
            result['checks'].append('day_change_clears_preview_empty_day')
            window.day_table.setCurrentCell(0,0)
            window.docs_table.setCurrentCell(0,0);window.docs_table.setCurrentCell(1,0)
            wait(lambda:not window.jobs)
            assert window.current_document().archive==archives[1] and window.viewer.pdf.data==data
            result['checks'].append('rapid_document_selection')
            dialog=SettingsDialog(settings,window)
            assert not hasattr(dialog,'target') and not hasattr(dialog.result_settings(),'target')
            dialog.close()
            result['checks'].append('source_only_settings_dialog')
            for style in QStyleFactory.keys(): apply_style(style)
            for surface in SURFACES:
                settings.ui_style=surface if surface!='Alapértelmezett' else 'Fusion'
                apply_settings_style(settings)
                for theme in THEME_NAMES:
                    set_theme(theme);app.processEvents()
                    assert not window.actions[0].icon().isNull() and window.viewer.pdf.data==data
            settings.ui_style=surface_theme if surface_theme!='Alapértelmezett' else 'Fusion'
            apply_settings_style(settings)
            set_theme('Crystal SVG');app.processEvents()
            result['checks'].append('all_surface_and_icon_themes')
            with_guard=[]
            try:
                for namespace in ('manager-selftest-'+str(os.getpid()),'viewer-selftest-'+str(os.getpid())):
                    guard=InstanceGuard(namespace);with_guard.append(guard);assert guard.acquire()
                second=InstanceGuard('viewer-selftest-'+str(os.getpid()));with_guard.append(second);assert not second.acquire()
            finally:
                for guard in reversed(with_guard): guard.close()
            result['checks'].append('independent_instance_guards')
            assert not (base/'DO-NOT-USE').exists()
            assert original=={p.name:p.read_bytes() for p in source.iterdir()}
            assert manager_bytes==settings_path().read_bytes()
            result['checks'].append('workspace_absent_source_and_manager_unchanged')
            screenshot=report.with_name(report.stem+'-screenshot.png')
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            assert window.grab().save(str(screenshot))
            result['screenshot']=screenshot.name
            window.close();window=None
        result['passed']=True
        result['windows1607_verified']=is1607
    except Exception:
        result['error']=traceback.format_exc()
    finally:
        if window:
            deadline=time.monotonic()+30
            while window.jobs and time.monotonic()<deadline:
                app.processEvents();time.sleep(.01)
            window.close()
        for key,value in previous.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['passed'] else 1
