import json
import os
import threading
import zipfile
from pathlib import Path
import pytest
from edpd.file_service import FileService
from edpd.models import EDPDError
from edpd.zip_service import ZipService
from edpd.extraction_transaction import recover


def packet(folders):
    source, target = folders
    with zipfile.ZipFile(source/'20261113_A.zip','w') as z:
        for name in ('a.pdf','b.pdf','c.pdf'): z.writestr(name,b'new-'+name.encode())
    (target/'a.pdf').write_bytes(b'old-a')
    day=ZipService().scan(source)[0]
    service=FileService(source,target)
    return service,day


@pytest.mark.parametrize('phase,count',[('before',0),('PDF-ek előkészítése',0),('PDF-ek előkészítése',1),
                                        ('PDF-ek véglegesítése',0),('PDF-ek véglegesítése',1),
                                        ('PDF-ek véglegesítése',2),('PDF-ek véglegesítése',3)])
@pytest.mark.parametrize('mode',['skip','overwrite'])
def test_cancellation_restores_original_packet(folders,phase,count,mode):
    service,day=packet(folders);source,target=folders
    original_source={p.name:p.read_bytes() for p in source.iterdir()}
    event=threading.Event()
    if phase=='before':event.set()
    def progress(text,done,total):
        if text==phase and done==count:event.set()
    result=service.extract(day,mode,expected_existing=service.extraction_plan(day).existing,progress=progress,cancel=event)
    # Skip has two candidates, so its final notification is 2 / 2, not 3 / 3.
    if mode=='skip' and phase=='PDF-ek véglegesítése' and count==3:
        assert '2 PDF kicsomagolva' in result
    else:
        assert 'megszakítva' in result
        assert {p.name:p.read_bytes() for p in target.glob('*.pdf')}=={'a.pdf':b'old-a'}
    assert not list(target.glob('.edpd-recovery-*'))
    assert original_source=={p.name:p.read_bytes() for p in source.iterdir()}


def test_stage_failure_never_publishes_partial_packet(folders,monkeypatch):
    service,day=packet(folders)
    import edpd.file_service as fs
    original=fs.read_document
    def fail(doc):
        if doc.name=='b.pdf':raise OSError('synthetic read failure')
        return original(doc)
    monkeypatch.setattr(fs,'read_document',fail)
    with pytest.raises(EDPDError,match='visszavontuk'):
        service.extract(day,'overwrite',expected_existing=service.extraction_plan(day).existing)
    assert {p.name:p.read_bytes() for p in folders[1].glob('*.pdf')}=={'a.pdf':b'old-a'}
    assert not list(folders[1].glob('.edpd-recovery-*'))


def test_commit_failure_restores_prior_overwrite(folders,monkeypatch):
    service,day=packet(folders);target=folders[1]
    (target/'b.pdf').write_bytes(b'old-b')
    original=os.replace
    def fail(source,destination):
        if Path(destination)==target/'b.pdf':raise OSError('synthetic commit failure')
        return original(source,destination)
    monkeypatch.setattr(os,'replace',fail)
    with pytest.raises(EDPDError,match='commit failure'):
        service.extract(day,'overwrite',expected_existing=service.extraction_plan(day).existing)
    assert {p.name:p.read_bytes() for p in target.glob('*.pdf')}=={'a.pdf':b'old-a','b.pdf':b'old-b'}
    assert not list(target.glob('.edpd-recovery-*'))


def test_failed_rollback_keeps_backups_and_explicit_recovery_retries(folders,monkeypatch):
    service,day=packet(folders);target=folders[1];event=threading.Event()
    original=os.replace
    def fail(source,destination):
        if str(source).endswith('.restore'):raise OSError('synthetic SMB recovery failure')
        return original(source,destination)
    monkeypatch.setattr(os,'replace',fail)
    def progress(text,done,total):
        if text=='PDF-ek véglegesítése' and done==1:event.set()
    with pytest.raises(EDPDError,match='a.pdf.*SMB recovery failure'):
        service.extract(day,'overwrite',expected_existing=service.extraction_plan(day).existing,progress=progress,cancel=event)
    recovery=next(target.glob('.edpd-recovery-*'))
    assert any(p.read_bytes()==b'old-a' for p in recovery.glob('*.bak'))
    assert json.loads((recovery/'journal.json').read_text())['records']
    with pytest.raises(EDPDError,match='helyreállítása'):
        service.deletion_plan()
    monkeypatch.setattr(os,'replace',original)
    recover(recovery)
    assert (target/'a.pdf').read_bytes()==b'old-a'
    assert not recovery.exists()


def test_other_user_modification_is_never_deleted_on_rollback(folders):
    service,day=packet(folders);target=folders[1];event=threading.Event()
    def progress(text,done,total):
        if text=='PDF-ek véglegesítése' and done==1:
            (target/'b.pdf').write_bytes(b'other user bytes')
            event.set()
    # In skip mode a.pdf is untouched and b.pdf is the first new publication.
    with pytest.raises(EDPDError,match='Másik folyamat'):
        service.extract(day,progress=progress,cancel=event)
    assert (target/'b.pdf').read_bytes()==b'other user bytes'
    recovery=next(target.glob('.edpd-recovery-*'))
    with pytest.raises(EDPDError,match='Másik folyamat'):recover(recovery)
    (target/'b.pdf').rename(target/'other-user-copy.txt')
    recover(recovery)
    assert (target/'other-user-copy.txt').read_bytes()==b'other user bytes'
    assert not list(target.glob('.edpd-recovery-*'))


def test_final_journal_failure_rolls_back_instead_of_reporting_false_success(folders,monkeypatch):
    service,day=packet(folders)
    import edpd.extraction_transaction as tx
    original=tx.save_journal;failed=[]
    def journal(folder,records):
        if any(r['state']=='committed' for r in records) and not failed:
            failed.append(True);raise OSError('synthetic final journal failure')
        return original(folder,records)
    monkeypatch.setattr(tx,'save_journal',journal)
    with pytest.raises(EDPDError,match='visszavontuk'):
        service.extract(day,'overwrite',expected_existing=service.extraction_plan(day).existing)
    assert {p.name:p.read_bytes() for p in folders[1].glob('*.pdf')}=={'a.pdf':b'old-a'}
    assert not list(folders[1].glob('.edpd-recovery-*'))


def test_recovery_cannot_write_into_source(folders):
    source,target=folders
    before=list(source.iterdir())
    with pytest.raises(EDPDError,match='forrásarchívumban'):
        recover(source/'.edpd-recovery-wrong',source,target)
    assert list(source.iterdir())==before
