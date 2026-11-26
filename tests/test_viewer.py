"""Archive-only regression tests: synthetic archives and isolated profiles."""
from datetime import date, timedelta
from dataclasses import asdict
from pathlib import Path
import json
import threading
import time
import zipfile
import pytest
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFileDialog, QMessageBox
from edpd.config import ViewerSettings, Settings, settings_path, viewer_settings_path, viewer_cache_directory
from edpd.ui.viewer_window import ViewerWindow, check_source, document_key
from edpd.zip_service import ZipService

TODAY = date(2026, 11, 16)


def wait(app, condition):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        app.processEvents()
        if condition(): return
        time.sleep(.005)
    assert condition(), 'Background operation timed out'


def archive(source, name, documents):
    path = source / name
    with zipfile.ZipFile(path, 'w') as z:
        for member, data in documents:
            z.writestr(member, data)
    return path


@pytest.fixture
def browser(app, tmp_path, pdf_bytes):
    source = tmp_path/'archive'; source.mkdir()
    archive(source, '20261116_A.zip', [('same.pdf', pdf_bytes), ('z.pdf', pdf_bytes)])
    archive(source, '20261116_B.zip', [('same.pdf', pdf_bytes)])
    archive(source, '20261115_EMPTY.zip', [])
    window = ViewerWindow(ViewerSettings(source=str(source)), today_provider=lambda:TODAY)
    window.show()
    wait(app, lambda: len(window.days)==2 and not window.jobs)
    yield window
    wait(app, lambda: not window.jobs and window.viewer.save_job is None)
    window.close()


def test_viewer_never_calls_workspace_services(app, tmp_path, pdf_bytes, monkeypatch):
    from edpd import file_service, state_service, processed_store, extraction_transaction, locking
    from edpd.ui.main_window import MainWindow
    def forbidden(*a, **k): raise AssertionError('Workspace service invoked')
    for obj, names in [(file_service, ['validate_paths', 'FileService']), (state_service, ['inventory','day_status']),
                       (processed_store, ['ProcessedStore']), (locking, ['workspace_lock']),
                       (extraction_transaction, ['recover']), (MainWindow, ['read_workspace'])]:
        for name in names: monkeypatch.setattr(obj, name, forbidden)
    source=tmp_path/'source';source.mkdir()
    z=archive(source,'20261116_A.zip',[('test.pdf',pdf_bytes)])
    original=z.read_bytes()
    Settings(source=str(source),target=str(tmp_path/'NONEXISTENT')).save()
    settings_before=settings_path().read_bytes()
    window=ViewerWindow(ViewerSettings(source=str(source)),today_provider=lambda:TODAY)
    try:
        window.show();wait(app,lambda:not window.jobs and len(window.days)==1)
        window.docs_table.setCurrentCell(0,0);wait(app,lambda:not window.jobs)
        assert window.viewer.pdf.data==pdf_bytes
        check_source(window.settings)
        assert not (tmp_path/'NONEXISTENT').exists()
        assert z.read_bytes()==original and settings_path().read_bytes()==settings_before
        assert window.viewer.workspace_path is None
    finally: window.close()


def test_viewer_ui_and_duplicate_identity(browser, app, pdf_bytes):
    w=browser
    assert [a.text() for a in w.operation_toolbar.actions()]==['Frissítés','Beállítások']
    assert w.day_table.columnCount()==3
    assert w.day_table.contextMenuPolicy()==Qt.DefaultContextMenu
    assert not hasattr(w,'extract') and not hasattr(w,'delete') and not hasattr(w,'processed_action')
    assert w.current_day().date==TODAY
    assert [d.name for d in w.documents]==['same.pdf','same.pdf','z.pdf']
    assert len(set(document_key(d) for d in w.documents))==3
    assert not w.access_notice.text()
    w.docs_table.setCurrentCell(1,0);wait(app,lambda:not w.jobs)
    assert w.viewer.pdf.data==pdf_bytes
    w.day_table.setCurrentCell(1,0)
    assert w.docs_table.rowCount()==0 and w.viewer.pdf is None and not w.viewer.save_action.isEnabled()


def test_refresh_preserves_reloads_and_removes_selected_document(browser, app, pdf_bytes):
    import fitz
    w=browser
    w.docs_table.setCurrentCell(0,0);wait(app,lambda:not w.jobs)
    w.viewer.move(2);w.viewer.zoom(1.25)
    original=w.viewer.pdf
    w.refresh();wait(app,lambda:not w.jobs)
    assert w.viewer.pdf is original and w.viewer.page==2
    assert w.current_document().name=='same.pdf'
    pdf=fitz.open();pdf.new_page();changed=pdf.tobytes();pdf.close()
    archive(Path(w.settings.source),'20261116_A.zip',[('same.pdf',changed)])
    w.refresh();wait(app,lambda:not w.jobs)
    assert w.viewer.pdf is not original and w.viewer.pdf.data==changed and w.viewer.page==0
    Path(w.settings.source,'20261116_A.zip').unlink()
    w.refresh();wait(app,lambda:not w.jobs)
    assert w.current_document() is None and w.viewer.pdf is None
    archive(Path(w.settings.source),'20261117_NEW.zip',[('new.pdf',pdf_bytes)])
    w.settings.history_days=None
    w.refresh();wait(app,lambda:not w.jobs)
    assert w.current_day().date==TODAY


def test_late_preview_cannot_overwrite_new_selection_or_day(browser, app, monkeypatch, pdf_bytes):
    import edpd.ui.viewer_window as module
    import fitz
    pdf=fitz.open();pdf.new_page();new_data=pdf.tobytes();pdf.close()
    w=browser;started=threading.Event();release=threading.Event()
    real=module.read_document
    def delayed(doc):
        if doc.archive.name.endswith('_A.zip'):
            started.set();assert release.wait(5)
        return real(doc)
    archive(Path(w.settings.source),'20261116_B.zip',[('same.pdf',new_data)])
    w.refresh();wait(app,lambda:not w.jobs)
    monkeypatch.setattr(module,'read_document',delayed)
    w.docs_table.setCurrentCell(0,0);wait(app,started.is_set)
    w.docs_table.setCurrentCell(1,0)
    release.set();wait(app,lambda:not w.jobs)
    assert w.current_document().archive.name.endswith('_B.zip')
    assert w.viewer.pdf.data==new_data
    started.clear();release.clear()
    w.docs_table.setCurrentCell(0,0);wait(app,started.is_set)
    w.day_table.setCurrentCell(1,0);release.set();wait(app,lambda:not w.jobs)
    assert w.viewer.pdf is None


def test_export_uses_original_bytes_and_rejects_archive_destination(browser, app, tmp_path, monkeypatch, pdf_bytes):
    monkeypatch.setattr('edpd.ui.pdf_viewer.documents_directory', lambda: str(tmp_path))
    w=browser;w.docs_table.setCurrentCell(0,0);wait(app,lambda:not w.jobs)
    output=tmp_path/'export.pdf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(output),'PDF'))
    w.viewer.save_action.trigger();wait(app,lambda:w.viewer.save_job is None)
    assert output.read_bytes()==pdf_bytes
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *a:errors.append(a[-1]))
    destination=Path(w.settings.source)/'forbidden.pdf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(destination),'PDF'))
    w.viewer.save_current()
    assert errors and not destination.exists()


def test_configuration_and_source_only_dialog(browser, tmp_path):
    from edpd.ui.settings_dialog import SettingsDialog
    from edpd.ui.about_dialog import AboutDialog
    w=browser;Settings(target='G:\\do-not-use').save();before=settings_path().read_bytes()
    w.settings.save();loaded=ViewerSettings.load()
    assert asdict(loaded)==asdict(w.settings) and not hasattr(loaded,'target')
    assert 'target' not in json.loads(viewer_settings_path().read_text())
    assert 'EDPD-Betekinto' in str(viewer_cache_directory())
    d=SettingsDialog(w.settings,w)
    assert not hasattr(d,'target') and not hasattr(d.result_settings(),'target')
    d.close()
    about=AboutDialog(w)
    assert 'EDPD Betekintő' in about.info.toPlainText();about.close()
    assert before==settings_path().read_bytes()


def test_source_failure_and_automatic_refresh(browser, app, monkeypatch):
    w=browser
    w.settings.source=str(Path(w.settings.source)/'missing')
    w.timer.start(10)
    wait(app,lambda:'nem olvasható' in w.access_notice.text() and not w.jobs)
    w.timer.stop()
    assert w.viewer.pdf is None


def test_browser_nested_duplicate_names_manager_collision_unchanged(tmp_path, pdf_bytes):
    z=archive(tmp_path,'20261116_A.zip',[('one/a.pdf',pdf_bytes),('two/a.pdf',pdf_bytes)])
    browser=ZipService(archive_browser=True).scan(tmp_path,today=TODAY)
    manager=ZipService().scan(tmp_path,today=TODAY)
    assert len(browser[0].documents)==2 and not browser[0].error
    assert manager[0].error and not manager[0].documents


def test_viewer_bootstrap_rejects_recovery_and_does_not_load_manager(tmp_path):
    import subprocess,sys,os
    result=subprocess.run([sys.executable,'-m','edpd.viewer_main','--recover-extraction','unused'],capture_output=True,text=True)
    assert result.returncode==2 and 'unrecognized arguments' in result.stderr
    script="from PySide2.QtWidgets import QApplication; from edpd.ui.viewer_window import ViewerWindow; from edpd.config import ViewerSettings; import sys; app=QApplication([]); w=ViewerWindow(ViewerSettings(),auto_refresh=False); assert 'edpd.ui.main_window' not in sys.modules"
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_configure_source_change_invalidates_old_preview(browser, app, tmp_path, monkeypatch, pdf_bytes):
    from edpd.ui.settings_dialog import SettingsDialog
    from PySide2.QtWidgets import QDialog
    from dataclasses import replace
    w=browser;new=tmp_path/'second-source';new.mkdir()
    archive(new,'20261116_NEW.zip',[('new.pdf',pdf_bytes)])
    w.docs_table.setCurrentCell(0,0);wait(app,lambda:not w.jobs)
    monkeypatch.setattr(SettingsDialog,'exec_',lambda self:QDialog.Accepted)
    monkeypatch.setattr(SettingsDialog,'result_settings',lambda self:replace(w.settings,source=str(new)))
    w.configure();wait(app,lambda:not w.jobs)
    assert w.settings.source==str(new) and w.viewer.pdf is None
    assert [d.name for d in w.documents]==['new.pdf']
    assert w.viewer.source_path==str(new) and w.viewer.workspace_path is None


def test_zip_safety_limits_crc_and_changed_metadata(tmp_path, pdf_bytes, monkeypatch):
    import edpd.zip_service as module
    from dataclasses import replace
    bad=archive(tmp_path,'20261116_BAD.zip',[('../unsafe.pdf',pdf_bytes)])
    service=ZipService(archive_browser=True)
    assert service.scan(tmp_path,today=TODAY)[0].error
    bad.unlink()
    z=archive(tmp_path,'20261116_GOOD.zip',[('good.pdf',pdf_bytes)])
    doc=service.scan(tmp_path,today=TODAY)[0].documents[0]
    assert module.read_document(doc)==pdf_bytes
    with pytest.raises(Exception,match='megváltozott'):
        module.read_document(replace(doc,crc=doc.crc^1))
    data=bytearray(z.read_bytes());offset=30+len('good.pdf')
    data[offset+10]^=1;z.write_bytes(data)
    with pytest.raises(zipfile.BadZipFile,match='CRC'):
        module.read_document(doc)
    monkeypatch.setattr(module,'MAX_PDF',10)
    service.invalidate([z]);assert service.scan(tmp_path,today=TODAY)[0].error


def test_manager_and_viewer_real_processes_run_together(app, tmp_path):
    import subprocess,sys,os
    source=tmp_path/'process-source';target=tmp_path/'process-target'
    source.mkdir();target.mkdir()
    Settings(source=str(source),target=str(target)).save()
    ViewerSettings(source=str(source)).save()
    processes=[]
    try:
        for module,name in [('edpd.main','manager'),('edpd.viewer_main','viewer')]:
            report=tmp_path/(name+'.json')
            # Real production identities are distinct; profiles and source are synthetic.
            process=subprocess.Popen([sys.executable,'-m',module,'--startup-report',str(report),
                                      '--startup-exit-ms','3000'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            processes.append(process)
        reports=[tmp_path/(name+'.json') for name in ('manager','viewer')]
        wait(app,lambda:all(p.exists() for p in reports))
        for process in processes: assert process.wait(timeout=20)==0
        records=[json.loads(p.read_text()) for p in reports]
        assert records[0]['display_name']=='EDPD Menedzser'
        assert records[1]['display_name']=='EDPD Betekintő'
        assert all(r['window_title'].startswith(r['display_name']) for r in records)
    finally:
        for process in processes:
            if process.poll() is None:process.kill();process.wait()



def test_daily_size_limit_blocks_preview(browser, app, monkeypatch):
    import edpd.zip_service as module
    monkeypatch.setattr(module, 'MAX_DAY', 1)
    browser.refresh(); wait(app, lambda:not browser.jobs)
    assert browser.current_day().error
    browser.docs_table.setCurrentCell(0, 0)
    app.processEvents()
    assert browser.viewer.pdf is None and not browser.jobs


def test_default_splitter_ratios_and_saved_positions(app, folders):
    settings = ViewerSettings(source=str(folders[0]), ui_style='Windows XP Luna Blue')
    window = ViewerWindow(settings, auto_refresh=False)
    window.show()
    for width in (1600, 1920):
        window.resize(width, 900)
        app.processEvents()
        horizontal, vertical = window.split.sizes(), window.left.sizes()
        assert horizontal[0] / sum(horizontal) == pytest.approx(.25, abs=.025)
        assert vertical[0] / sum(vertical) == pytest.approx(.52, abs=.025)
    window.split.moveSplitter(640, 1)
    window.left.moveSplitter(300, 1)
    app.processEvents()
    horizontal, vertical = window.split.sizes(), window.left.sizes()
    assert horizontal[0] == pytest.approx(640, abs=4)
    assert vertical[0] == pytest.approx(300, abs=4)
    window.close()

    reopened = ViewerWindow(ViewerSettings.load(), auto_refresh=False)
    reopened.show()
    try:
        app.processEvents()
        for splitter, original in ((reopened.split, horizontal), (reopened.left, vertical)):
            sizes = splitter.sizes()
            assert sizes[0] / sum(sizes) == pytest.approx(original[0] / sum(original), abs=.02)
    finally:
        reopened.close()


def test_table_alignment_remains_after_refresh(browser, app):
    for _ in range(2):
        for table, center in ((browser.day_table, {0, 2}), (browser.docs_table, {1, 2})):
            assert table.rowCount() > 0
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    alignment = Qt.AlignCenter if col in center else Qt.AlignLeft | Qt.AlignVCenter
                    assert table.item(row, col).textAlignment() == int(alignment)
        browser.refresh()
        wait(app, lambda: not browser.jobs)


def test_toolbar_about_stays_at_right_and_tracks_theme(browser, app, monkeypatch):
    from PySide2.QtCore import QPoint
    from edpd.ui.about_dialog import AboutDialog
    from edpd.ui.icons import icon, manager, set_theme

    button = browser.about_button
    assert browser.menuWidget() is None
    assert button.toolButtonStyle() == Qt.ToolButtonIconOnly
    assert button.iconSize().width() == button.iconSize().height() == 40
    assert button.toolTip() == 'Névjegy'
    for width in (1600, 850):
        browser.resize(width, 800)
        app.processEvents()
        controls = browser.toolbar_controls
        assert button.isVisible()
        assert controls.width() - button.geometry().right() <= 2
        actions_edge = browser.operation_toolbar.mapToGlobal(QPoint(0, 0)).x()
        assert actions_edge < button.mapToGlobal(QPoint(0, 0)).x()

    dialogs = []
    monkeypatch.setattr(AboutDialog, 'exec_', lambda dialog: dialogs.append(dialog))
    button.click()
    assert len(dialogs) == 1 and 'EDPD Betekintő' in dialogs[0].info.toPlainText()
    previous = manager().name
    try:
        original = button.icon().cacheKey()
        set_theme('SE98')
        assert icon('about').cacheKey() == button.icon().cacheKey() != original
    finally:
        set_theme(previous)


def test_access_notice_only_allocates_space_for_errors(app, folders):
    source, _ = folders
    window = ViewerWindow(ViewerSettings(source=str(source / 'missing'), ui_style='Windows XP Luna Blue'),
                          auto_refresh=False)
    window.show()
    app.processEvents()

    def gap(table):
        title = table.parentWidget().title_label
        return table.y() - title.geometry().bottom() - 1

    try:
        assert not window.access_notice.isVisible()
        assert gap(window.day_table) == gap(window.docs_table)
        normal_gap = gap(window.day_table)
        window.refresh()
        wait(app, lambda: not window.jobs)
        assert window.access_notice.isVisible()
        assert 'nem olvasható' in window.access_notice.text()
        wait(app, lambda: gap(window.day_table) > normal_gap)

        window.settings.source = str(source)
        window.refresh()
        wait(app, lambda: not window.jobs)
        assert not window.access_notice.isVisible() and not window.access_notice.text()
        wait(app, lambda: gap(window.day_table) == normal_gap)
        assert not window.statusBar().currentMessage()
    finally:
        window.close()


@pytest.mark.parametrize('style', ['Fusion', 'Windows', 'WindowsVista', 'Windows XP Luna Blue',
                                   'Longhorn Blue', 'Longhorn Slate'])
def test_both_selected_rows_stay_visible_without_focus(app, folders, pdf_bytes, style):
    from PySide2.QtGui import QColor, QPalette
    from PySide2.QtWidgets import QStyleFactory

    from edpd.surface_styles import CUSTOM_SURFACES

    if style not in CUSTOM_SURFACES and style.casefold() not in {key.casefold() for key in QStyleFactory.keys()}:
        pytest.skip(f'{style} is unavailable on this platform')

    source, _ = folders
    archive(source, '20261116_A.zip', [('one.pdf', pdf_bytes)])
    archive(source, '20261115_B.zip', [('two.pdf', pdf_bytes)])
    window = ViewerWindow(ViewerSettings(source=str(source), ui_style=style), today_provider=lambda: TODAY)
    window.show()
    window.activateWindow()
    day, docs = window.day_table, window.docs_table

    for table in (day, docs):
        palette = table.palette()
        palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor('#eaeaea'))
        palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor('#5a5a5a'))
        table.setPalette(palette)

    def row_background(table, row=0):
        viewport = table.viewport()
        picture = viewport.grab()
        bitmap = picture.toImage()
        dpr = picture.devicePixelRatio()
        colours = []
        for column in range(table.columnCount()):
            rect = table.visualItemRect(table.item(row, column))
            x = int((rect.right() - 4) * dpr)
            y = int((rect.top() + 4) * dpr)
            assert bitmap.rect().contains(x, y)
            colours.append(bitmap.pixelColor(x, y).getRgb()[:3])
        return colours

    def assert_same_highlight(focused, unfocused):
        # A native focus indicator can tint the current cell slightly.
        for active, inactive in zip(focused, unfocused):
            assert max(abs(a - b) for a, b in zip(active, inactive)) <= 18, (focused, unfocused)

    try:
        wait(app, lambda: day.rowCount() == 2 and not window.jobs)
        day.setFocus()
        wait(app, day.hasFocus)
        day_focused = row_background(day)
        day_unselected = row_background(day, 1)
        assert all(highlight != plain for highlight, plain in zip(day_focused, day_unselected))

        docs.setCurrentCell(0, 0)
        docs.setFocus()
        wait(app, lambda: docs.hasFocus() and window.viewer.pdf and not window.jobs)
        doc_focused = row_background(docs)
        assert day.currentRow() == 0 and not day.hasFocus()
        assert_same_highlight(day_focused, row_background(day))

        day.setFocus()
        wait(app, day.hasFocus)
        assert_same_highlight(doc_focused, row_background(docs))
        assert docs.currentRow() == 0

        # The refresh path must retain both logical selections and their paint.
        window.refresh()
        wait(app, lambda: not window.jobs)
        assert day.currentRow() == docs.currentRow() == 0
        assert_same_highlight(day_focused, row_background(day))
        assert_same_highlight(doc_focused, row_background(docs))

        day.setCurrentCell(1, 0)
        app.processEvents()
        assert day.currentRow() == 1
        assert_same_highlight(day_focused, row_background(day, 1))
        assert row_background(day) != day_focused
        assert docs.item(0, 0).text() == 'two.pdf'

        from edpd.ui.appearance import apply_settings_style
        for table in (day, docs):
            table.setPalette(QPalette())
        apply_settings_style(ViewerSettings(ui_style='Longhorn Blue' if style == 'Windows XP Luna Blue'
                                           else 'Windows XP Luna Blue'))
        app.processEvents()
        changed = row_background(day, 1)
        assert all(highlight != plain for highlight, plain in zip(changed, row_background(day)))
        docs.setFocus()
        wait(app, docs.hasFocus)
        assert_same_highlight(changed, row_background(day, 1))
    finally:
        window.close()
