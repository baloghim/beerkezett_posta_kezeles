from pathlib import Path
import fitz
import pytest
from PySide2.QtWidgets import QFileDialog,QMessageBox
from edpd.pdf_export import save_pdf,target_stamp
from edpd.ui.pdf_viewer import PDFViewer
from edpd.ui.main_window import MainWindow
from edpd.config import Settings
from edpd.zip_service import ZipService
from test_ui import wait_for
import zipfile
from datetime import date


def test_export_preserves_original_multpage_bytes_and_guards_folders(folders,pdf_bytes,tmp_path):
    source,target=folders;out=tmp_path/'export.pdf'
    save_pdf(pdf_bytes,out,source,target)
    assert out.read_bytes()==pdf_bytes
    with fitz.open(out) as doc:assert doc.page_count==3
    for forbidden in (source/'no.pdf',target/'no.pdf'):
        with pytest.raises(Exception,match='kívül'):save_pdf(pdf_bytes,forbidden,source,target)
        assert not forbidden.exists()
    out.write_bytes(b'existing');before=target_stamp(out);out.write_bytes(b'other user changed file')
    with pytest.raises(Exception,match='megváltozott'):save_pdf(pdf_bytes,out,source,target,before)
    assert out.read_bytes()==b'other user changed file'


@pytest.mark.parametrize('response',['cancel_dialog','deny_overwrite','confirm_overwrite'])
def test_save_dialog_filename_cancel_and_confirm(app,pdf_bytes,tmp_path,monkeypatch,response):
    viewer=PDFViewer();viewer.show()
    assert not viewer.save_action.isEnabled()
    viewer.open_data(pdf_bytes,'eredeti.pdf')
    out=tmp_path/'saved.pdf';out.write_bytes(b'old')
    suggested=[]
    def dialog(*args,**kwargs):
        suggested.append(args[2]);return ('','') if response=='cancel_dialog' else (str(out),'PDF')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',dialog)
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Yes if response=='confirm_overwrite' else QMessageBox.No)
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *a:errors.append(a[-1]))
    viewer.save_action.trigger();wait_for(app,lambda:viewer.save_job is None)
    assert suggested==['eredeti.pdf']
    assert out.read_bytes()==(pdf_bytes if response=='confirm_overwrite' else b'old')
    assert not errors
    viewer.pdf.close();viewer.close()


def test_direct_zip_preview_exports_entire_pdf_with_original_name(app,folders,pdf_bytes,tmp_path,monkeypatch):
    source,target=folders
    with zipfile.ZipFile(source/f'{date.today():%Y%m%d}_A.zip','w') as archive:archive.writestr('nested/postai-level.pdf',pdf_bytes)
    window=MainWindow(Settings(source=str(source),target=str(target)));window.show()
    wait_for(app,lambda:window.days and not window.jobs)
    window.open_archive_document(window.days[0].documents[0]);wait_for(app,lambda:not window.jobs and window.viewer.pdf)
    assert window.viewer.filename=='postai-level.pdf'
    out=tmp_path/'outside.pdf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(out),'PDF'))
    window.viewer.save_current();wait_for(app,lambda:window.viewer.save_job is None)
    assert out.read_bytes()==pdf_bytes and not list(target.glob('*.pdf'))
    assert window.docs_table.rowCount()==0
    assert window.viewer.fit_mode=='width'
    window.close()


def test_loaded_document_keeps_original_archive_guard_after_settings_change(app,folders,pdf_bytes,tmp_path,monkeypatch):
    source,target=folders
    viewer=PDFViewer();viewer.set_paths(source,target);viewer.open_data(pdf_bytes,'eredeti.pdf')
    changed_source=tmp_path/'new-source';changed_source.mkdir()
    changed_target=tmp_path/'new-target';changed_target.mkdir()
    viewer.set_paths(changed_source,changed_target)
    forbidden=source/'must-not-exist.pdf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(forbidden),'PDF'))
    errors=[];monkeypatch.setattr(QMessageBox,'warning',lambda *a:errors.append(a[-1]))
    viewer.save_current()
    assert errors and not forbidden.exists() and viewer.save_job is None
    viewer.pdf.close();viewer.close()


def test_invalid_replacement_keeps_original_pdf_filename(app,pdf_bytes):
    viewer=PDFViewer();viewer.open_data(pdf_bytes,'original.pdf')
    with pytest.raises(Exception):viewer.open_data(b'broken','broken.pdf')
    assert viewer.filename=='original.pdf' and viewer.pdf.data==pdf_bytes
    viewer.pdf.close();viewer.close()
