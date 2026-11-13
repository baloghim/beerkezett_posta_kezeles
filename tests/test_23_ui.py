from datetime import date,timedelta
import threading
import zipfile
from pathlib import Path
import pytest
from PySide2.QtCore import Qt,QTimer
from PySide2.QtGui import QColor
from PySide2.QtWidgets import QMenu
from edpd.config import Settings
from edpd.models import Capabilities
from edpd.processed_store import ProcessedStore,packet_id
from edpd.ui.main_window import MainWindow
from edpd.file_service import FileService
from test_ui import wait_for
from test_extraction_flow import setup


def test_workspace_day_order_selection_and_responsive_columns(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    target=folders[1]
    for name in ('z.pdf','a.pdf','b.pdf','unknown.pdf'):(target/name).write_bytes(pdf_bytes)
    window.refresh();wait_for(app,lambda:not window.jobs)
    origins={'z.pdf':'2026.11.13.','a.pdf':'2026.11.13.','b.pdf':'2026.11.12.'}
    window.populate_workspace(origins)
    assert [window.docs_table.horizontalHeaderItem(i).text() for i in range(3)]==['Nap','Fájlnév','Méret']
    assert window.work_keys==['a.pdf','z.pdf','b.pdf','unknown.pdf']
    assert window.docs_table.item(3,0).text()=='Ismeretlen'
    window.docs_table.selectRow(1);wait_for(app,lambda:window.viewer.pdf and not window.jobs)
    pdf=window.viewer.pdf
    window.populate_workspace({**origins,'z.pdf':'2026.11.01.'})
    assert window.work_keys[window.docs_table.currentRow()]=='z.pdf'
    assert window.viewer.pdf is pdf and window.viewer.filename=='z.pdf'
    assert window.docs_table.item(window.docs_table.currentRow(),1).toolTip()=='z.pdf'
    for table,ratios in [(window.day_table,(.18,.44,.10,.28)),(window.docs_table,(.21,.64,.15))]:
        table.apply_widths()
        assert sum(table.columnWidth(i) for i in range(table.columnCount()))==table.viewport().width()
        for i,ratio in enumerate(ratios):
            assert table.columnWidth(i)>=table.minimum_widths[i]
            if all(table.viewport().width()*r>=m for r,m in zip(ratios,table.minimum_widths)):
                assert table.columnWidth(i)==pytest.approx(table.viewport().width()*ratio,abs=3)
        width=table.columnWidth(1);table.setColumnWidth(1,width+30)
        custom=table.ratios;table.apply_widths();assert table.ratios==custom
        assert table.verticalHeader().defaultSectionSize()>=table.fontMetrics().height()+10
        assert table.item(0,0).textAlignment() & Qt.AlignVCenter
    assert window.main_toolbar.iconSize().width()==40
    assert window.workspace_panel.title_label.font().bold()
    assert not window.styleSheet() and not errors
    window.close()


def test_origin_search_button_disappears_on_completion(app,folders,pdf_bytes,monkeypatch):
    source,target=folders
    (target/'old.pdf').write_bytes(pdf_bytes)
    old=date.today()-timedelta(days=100)
    with zipfile.ZipFile(source/f'{old:%Y%m%d}_old.zip','w') as z:z.writestr('old.pdf',pdf_bytes)
    window=MainWindow(Settings(source=str(source),target=str(target)));window.show()
    wait_for(app,lambda:window.origin_pending and not window.jobs)
    assert window.origin_button.isVisible()
    window.origin_button.click();wait_for(app,lambda:not window.origin_pending and not window.jobs)
    assert not window.origin_button.isVisible()
    assert window.docs_table.item(0,0).text()==old.strftime('%Y.%m.%d.')
    window.close()


def test_local_processed_marks_menu_target_and_viewer_exclusion(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    store=ProcessedStore(*folders);day=window.days[0]
    before={p.name:p.read_bytes() for p in folders[0].iterdir()}
    menu_items=[]
    def menu_exec(menu,pos):
        menu_items.extend(a.text() for a in menu.actions());menu.actions()[-1].trigger()
    def menu_factory(parent):
        menu=QMenu(parent)
        menu.exec_=lambda pos:menu_exec(menu,pos)
        return menu
    monkeypatch.setattr('edpd.ui.main_window.QMenu',menu_factory)
    point=window.day_table.visualItemRect(window.day_table.item(0,0)).center()
    window.show_day_menu(point);wait_for(app,lambda:not window.jobs)
    assert menu_items==['ZIP-csomag PDF-jeinek megtekintése…','Feldolgozva']
    assert packet_id(folders[0],day) in store.read()
    assert window.day_table.item(0,3).text()=='Feldolgozva • Nincs kicsomagolva'
    assert all(window.day_table.item(0,c).foreground().color()==QColor('#167235') for c in range(4))
    assert not list(folders[1].glob('*.pdf'))
    window.close()
    restarted=MainWindow(Settings(source=str(folders[0]),target=str(folders[1]),history_days=None));restarted.show()
    wait_for(app,lambda:restarted.days and not restarted.jobs)
    assert restarted.processed_action.text()=='Feldolgozás visszavonása'
    assert 'Feldolgozva' in restarted.day_table.item(0,3).text()
    restarted.mark_day(restarted.days[0]);wait_for(app,lambda:not restarted.jobs)
    assert not store.read();restarted.close()
    viewer=MainWindow(Settings(source=str(folders[0]),target=str(folders[1])),Capabilities.viewer());viewer.show()
    wait_for(app,lambda:viewer.days and not viewer.jobs)
    assert not viewer.processed_action.isVisible()
    viewer.mark_day(viewer.days[0]);assert not store.read()
    viewer.close()
    assert before=={p.name:p.read_bytes() for p in folders[0].iterdir()} and not errors


def test_processed_store_separates_offices_and_preserves_corrupt_file(folders,tmp_path):
    source,target=folders
    with zipfile.ZipFile(source/'20261113_A.zip','w') as z:z.writestr('a.pdf',b'a')
    from edpd.zip_service import ZipService
    day=ZipService().scan(source)[0];store=ProcessedStore(source,target)
    store.set_processed(day,True)
    other=tmp_path/'other-office';other.mkdir()
    assert packet_id(source,day)!=packet_id(other,day)
    assert packet_id(source,day) in ProcessedStore(source,target).read()
    store.path.write_text('corrupt')
    with pytest.raises(Exception):store.set_processed(day,False)
    assert store.path.read_text()=='corrupt'


def test_cancel_dialog_remains_open_until_rollback_finishes(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    published,continue_commit,rolling,continue_rollback=(threading.Event() for _ in range(4))
    original_extract=FileService.extract
    def extract(service,*a,**kwargs):
        notify=kwargs['progress']
        def progress(text,done,total):
            notify(text,done,total)
            if text=='PDF-ek véglegesítése' and done==1:
                published.set();assert continue_commit.wait(5)
        kwargs['progress']=progress
        return original_extract(service,*a,**kwargs)
    monkeypatch.setattr(FileService,'extract',extract)
    original_unlink=Path.unlink
    def unlink(path,*a,**k):
        if path.parent==folders[1] and path.suffix=='.pdf':
            rolling.set();assert continue_rollback.wait(5)
        return original_unlink(path,*a,**k)
    monkeypatch.setattr(Path,'unlink',unlink)
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(5)
    try:
        window.extract();wait_for(app,lambda:published.is_set())
        dialog=window.extraction_dialog
        assert dialog.isModal() and dialog.isVisible()
        dialog.cancel_button.click();assert window.cancel_extraction.is_set()
        continue_commit.set();wait_for(app,lambda:rolling.is_set() and len(ticks)>3)
        assert dialog.isVisible() and not dialog.cancel_button.isEnabled()
        assert window.extracting
    finally:
        continue_commit.set();continue_rollback.set();timer.stop()
    wait_for(app,lambda:not window.jobs and not window.extracting)
    assert not dialog.isVisible() and not list(folders[1].glob('*.pdf')) and not errors
    assert 'megszakítva' in window.statusBar().currentMessage()
    window.close()


def test_context_menu_marks_clicked_day_instead_of_previous_selection(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    old=date.today()-timedelta(days=1)
    with zipfile.ZipFile(folders[0]/f'{old:%Y%m%d}_other.zip','w') as z:z.writestr('other.pdf',pdf_bytes)
    window.refresh();wait_for(app,lambda:len(window.days)==2 and not window.jobs)
    window.day_table.selectRow(0)
    clicked=window.days[1]
    def menu_factory(parent):
        menu=QMenu(parent)
        menu.exec_=lambda pos:menu.actions()[-1].trigger()
        return menu
    monkeypatch.setattr('edpd.ui.main_window.QMenu',menu_factory)
    window.show_day_menu(window.day_table.visualItemRect(window.day_table.item(1,0)).center())
    wait_for(app,lambda:not window.jobs)
    keys=ProcessedStore(*folders).read()
    assert packet_id(folders[0],clicked) in keys
    assert packet_id(folders[0],window.days[0]) not in keys
    assert not errors
    window.close()


def test_viewer_cannot_write_local_marks_in_service(folders):
    from edpd.zip_service import ZipService
    with zipfile.ZipFile(folders[0]/'20261113_A.zip','w') as z:z.writestr('a.pdf',b'a')
    day=ZipService().scan(folders[0])[0]
    store=ProcessedStore(*folders,Capabilities.viewer())
    with pytest.raises(Exception,match='tiltott'):store.set_processed(day,True)
    assert not store.path.exists()


def test_local_marks_use_same_identity_through_source_directory_alias(folders,tmp_path):
    from edpd.zip_service import ZipService
    source,target=folders
    with zipfile.ZipFile(source/'20261113_A.zip','w') as z:z.writestr('a.pdf',b'a')
    alias=tmp_path/'source-alias'
    try:alias.symlink_to(source,target_is_directory=True)
    except OSError:pytest.skip('A tesztfiók nem hozhat létre könyvtárhivatkozást')
    day=ZipService().scan(source)[0]
    store=ProcessedStore(alias,target);store.set_processed(day,True)
    assert packet_id(alias,day)==packet_id(source,day)
    assert packet_id(alias,day) in ProcessedStore(source,target).read()
