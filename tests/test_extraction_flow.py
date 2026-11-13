import json
import threading
import zipfile
from datetime import date
from pathlib import Path

import pytest
from PySide2.QtCore import Qt, QTimer
from PySide2.QtTest import QTest
from PySide2.QtWidgets import QMessageBox, QLineEdit, QStyleFactory
from edpd.config import Settings
from edpd.file_service import FileService
from edpd.locking import workspace_lock
from edpd.models import EDPDError
from edpd.ui.main_window import MainWindow
from edpd.ui.settings_dialog import SettingsDialog
from edpd.zip_service import ZipService
from test_ui import wait_for


def setup(app, folders, pdf_bytes, monkeypatch):
    source, target=folders
    with zipfile.ZipFile(source/f'{date.today():%Y%m%d}_test.zip','w') as z:
        for name in ('one.pdf','two.pdf','three.pdf'): z.writestr(name,pdf_bytes)
        z.writestr('summary.csv','ignored')
    errors=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *a: errors.append(a[-1]))
    window=MainWindow(Settings(source=str(source),target=str(target)))
    window.show();wait_for(app,lambda: bool(window.days) and not window.jobs)
    return window,errors


def test_old_settings_ignore_removed_keys_without_touching_old_folder(tmp_path, app):
    old=tmp_path/'shared';old.mkdir();marks=old/'completed.json';marks.write_bytes(b'legacy-state')
    path=tmp_path/'settings.json';path.write_text(json.dumps({'shared_data':str(old),'qt_style':'WindowsVista'}))
    settings=Settings.load(path);assert not hasattr(settings,'shared_data')
    settings.save(path);assert 'shared_data' not in json.loads(path.read_text())
    assert marks.read_bytes()==b'legacy-state'
    dialog=SettingsDialog(settings,None)
    assert len(dialog.findChildren(QLineEdit))==2
    assert not hasattr(dialog,'shared_data')
    dialog.reject()


def test_vista_label_retains_actual_key(app,monkeypatch):
    # WindowsVista is not installed on every platform; model it without applying it.
    monkeypatch.setattr(QStyleFactory,'keys',lambda:['Fusion','WindowsVista','Windows'])
    dialog=SettingsDialog(Settings(),None)
    i=dialog.style_combo.findText('Vista');assert i>=0
    assert dialog.style_combo.itemData(i)=='WindowsVista'
    dialog.style_combo.setCurrentIndex(i)
    assert dialog.result_settings().qt_style=='WindowsVista'
    assert dialog.style_combo.findText('WindowsVista')==-1
    dialog.reject()


def test_empty_extract_no_prompt_no_result_modal(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    def unexpected(*a): raise AssertionError('Unexpected modal dialog')
    monkeypatch.setattr(QMessageBox,'exec_',unexpected)
    monkeypatch.setattr(QMessageBox,'information',unexpected)
    assert not hasattr(window,'mark_action') and not hasattr(window,'toggle_done')
    window.extract()
    assert window.extracting and window.extraction_bar.isVisible()
    wait_for(app,lambda: not window.extracting and not window.jobs)
    assert len(list(folders[1].glob('*.pdf')))==3
    assert not list(folders[1].glob('*.csv'))
    assert window.day_table.item(0,3).text()=='Kicsomagolva'
    assert not window.extraction_bar.isVisible() and not errors
    assert '3 PDF kicsomagolva' in window.statusBar().currentMessage()
    window.close()


def test_already_complete_only_informs_from_current_disk(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    for name in ('one.pdf','two.pdf','three.pdf'): (folders[1]/name).write_bytes(pdf_bytes)
    # UI still shows an empty target; preparation must inspect disk, not that snapshot.
    assert not window.files
    monkeypatch.setattr(FileService,'extract',lambda *a,**k: pytest.fail('Re-extraction'))
    messages=[];monkeypatch.setattr(QMessageBox,'information',lambda *a:messages.append(a[-1]))
    window.extract();wait_for(app,lambda: not window.extracting and not window.jobs)
    assert messages==['A kiválasztott nap dokumentumai már megtalálhatók a munkamappában.']
    assert not errors;window.close()


@pytest.mark.parametrize('choice',['skip','overwrite','cancel'])
def test_partial_choices_and_counts(app,folders,pdf_bytes,monkeypatch,choice):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    path=folders[1]/'one.pdf';path.write_bytes(b'original')
    seen=[];buttons={}
    def execute(box):
        seen.append(box.text())
        assert '3 PDF-ből 1' in box.text() and '2 hiányzik' in box.text()
        by_name={b.text():b for b in box.buttons()}
        assert set(by_name)=={'Meglévők kihagyása, hiányzók kicsomagolása','Meglévők felülírása','Mégse'}
        assert box.defaultButton() is by_name['Meglévők kihagyása, hiányzók kicsomagolása']
        buttons['chosen']=by_name[{'skip':'Meglévők kihagyása, hiányzók kicsomagolása','overwrite':'Meglévők felülírása','cancel':'Mégse'}[choice]]
        return 0
    monkeypatch.setattr(QMessageBox,'exec_',execute)
    monkeypatch.setattr(QMessageBox,'clickedButton',lambda box:buttons['chosen'])
    window.extract();wait_for(app,lambda:not window.extracting and not window.jobs)
    assert len(seen)==1 and not errors
    assert len(list(folders[1].glob('*.pdf')))==(1 if choice=='cancel' else 3)
    assert path.read_bytes()==(pdf_bytes if choice=='overwrite' else b'original')
    window.close()


def test_progress_real_completion_responsive_and_duplicate_doubleclick_blocked(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    import edpd.file_service as service_module
    original=service_module.read_document
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def delayed(doc):
        calls.append(doc.name)
        if len(calls)==2:
            entered.set();assert release.wait(5)
        return original(doc)
    monkeypatch.setattr(service_module,'read_document',delayed)
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(5)
    try:
        window.day_table.setFocus()
        rect=window.day_table.visualItemRect(window.day_table.item(0,0))
        QTest.mouseClick(window.day_table.viewport(),Qt.LeftButton,pos=rect.center())
        assert not window.extracting
        QTest.mouseDClick(window.day_table.viewport(),Qt.LeftButton,pos=rect.center())
        wait_for(app,lambda:entered.is_set() and window.extraction_bar.value()==1 and len(ticks)>2)
        assert window.extraction_bar.maximum()==3
        assert '1 / 3' in window.extraction_label.text()
        assert not window.actions[0].isEnabled() and not window.actions[1].isEnabled()
        window.extract();window.day_table.itemDoubleClicked.emit(window.day_table.item(0,0))
        assert len(calls)==2
        window.viewer.open_data(pdf_bytes)
        window.viewer.move(1);assert window.viewer.page==1
    finally:
        release.set();timer.stop()
    wait_for(app,lambda:not window.jobs and not window.extracting)
    assert len(calls)==3 and not errors
    window.close()


def test_error_hides_progress_and_keeps_details(app,folders,pdf_bytes,monkeypatch):
    window,errors=setup(app,folders,pdf_bytes,monkeypatch)
    def fail(*a,**k):raise OSError('Synthetic network failure')
    monkeypatch.setattr(FileService,'extract',fail)
    window.extract();wait_for(app,lambda:errors and not window.jobs)
    assert 'Synthetic network failure' in errors[0]
    assert not window.extracting and not window.extraction_bar.isVisible()
    window.close()


def test_overwrite_approval_rechecked_under_lock(folders):
    source,target=folders
    with zipfile.ZipFile(source/'20261113_test.zip','w') as z:
        z.writestr('a.pdf',b'new');z.writestr('b.pdf',b'b')
    day=ZipService().scan(source)[0];service=FileService(source,target)
    path=target/'a.pdf';path.write_bytes(b'old');plan=service.extraction_plan(day)
    path.write_bytes(b'changed by other user')
    with pytest.raises(EDPDError,match='megváltozott'):
        service.extract(day,'overwrite',expected_existing=plan.existing)
    assert path.read_bytes()==b'changed by other user' and not (target/'b.pdf').exists()
    with workspace_lock(target):
        with pytest.raises(EDPDError,match='foglalt'):
            service.extract(day)


def test_skip_race_never_overwrites_and_full_target_avoids_history(folders,monkeypatch):
    source,target=folders
    with zipfile.ZipFile(source/'20261113_test.zip','w') as z:z.writestr('a.pdf',b'new')
    (source/'20000101_broken.zip').write_bytes(b'broken')
    service=FileService(source,target);day=ZipService().scan(source,dates={date(2026,11,13)})[0]
    assert service.extraction_plan(day).present==0
    (target/'a.pdf').write_bytes(b'other user')
    opened=[];original=zipfile.ZipFile
    def spy(path,*a,**k):opened.append(Path(path).name);return original(path,*a,**k)
    monkeypatch.setattr(zipfile,'ZipFile',spy)
    assert 'már megtalálhatók' in service.extract(day)
    assert (target/'a.pdf').read_bytes()==b'other user'
    assert '20000101_broken.zip' not in opened
