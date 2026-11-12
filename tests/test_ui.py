import time
import zipfile
from PySide6.QtWidgets import QMessageBox
from edpd.config import Settings
from edpd.ui.main_window import MainWindow
from edpd.ui.pdf_viewer import PDFViewer
from edpd.ui.settings_dialog import SettingsDialog, check_settings


def wait_for(app, condition, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError('A háttérművelet nem fejeződött be')


def test_viewer_paging_zoom(app, pdf_bytes):
    viewer = PDFViewer()
    viewer.resize(900, 800)
    viewer.show()
    app.processEvents()
    viewer.open_data(pdf_bytes)
    viewer.move(2)
    assert viewer.page_label.text().strip() == '3 / 3'
    viewer.move(50)
    assert viewer.page == 2
    viewer.zoom(1.25)
    viewer.fit('width')
    assert viewer.label.pixmap().width() > 500
    viewer.pdf.close()
    viewer.close()


def test_main_workflow_and_settings(app, folders, pdf_bytes, tmp_path, monkeypatch):
    source, target = folders
    monkeypatch.setenv('APPDATA', str(tmp_path / 'profile'))
    with zipfile.ZipFile(source / '20261111_NEAK_1.zip', 'w') as z:
        z.writestr('nested/levél.pdf', pdf_bytes)
        z.writestr('sum.csv', 'ignored')
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    window = MainWindow(Settings(source=str(source), target=str(target)))
    window.show()
    wait_for(app, lambda: len(window.days) == 1 and not window.jobs)
    assert window.docs_table.rowCount() == 1
    window.docs_table.selectRow(0)
    wait_for(app, lambda: window.viewer.pdf is not None and not window.jobs)
    assert not list(target.iterdir())
    window.viewer.move(1)
    window.refresh()
    wait_for(app, lambda: not window.jobs)
    assert window.viewer.page == 1
    dialog = SettingsDialog(window.settings, window)
    dialog.slider.setValue(12)
    assert dialog.result_settings().refresh_minutes == 60
    assert check_settings(dialog.result_settings()).target == str(target)
    assert not errors
    window.close()
    assert Settings.load(tmp_path / 'profile' / 'EDPD' / 'settings.json').source == str(source)


def test_print_cancel_never_renders(app, pdf_bytes, monkeypatch):
    from PySide6.QtPrintSupport import QPrintDialog
    from PySide6.QtWidgets import QDialog
    import edpd.print_service as printing
    from edpd.pdf_service import PDFService
    pdf = PDFService(pdf_bytes)
    monkeypatch.setattr(QPrintDialog, 'exec', lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(printing, 'render_to_printer', lambda *args: (_ for _ in ()).throw(AssertionError('Nyomtatás megszakítás után')))
    printing.print_pdf(pdf, None)
    pdf.close()


def test_ui_extract_delete_and_clear(app, folders, pdf_bytes, tmp_path, monkeypatch):
    source, target = folders
    monkeypatch.setenv('APPDATA', str(tmp_path / 'profile'))
    with zipfile.ZipFile(source / '20261111_test.zip', 'w') as z:
        z.writestr('letter.pdf', pdf_bytes)
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: 0)
    monkeypatch.setattr(QMessageBox, 'clickedButton', lambda self: next(b for b in self.buttons() if b.text() == 'Meglévők kihagyása'))
    window = MainWindow(Settings(source=str(source), target=str(target)))
    window.show()
    wait_for(app, lambda: bool(window.days) and not window.jobs)
    window.extract()
    wait_for(app, lambda: (target / 'letter.pdf').exists() and not window.jobs)
    assert window.day_table.item(0, 3).text() == 'Kicsomagolva'
    window.delete(False)
    wait_for(app, lambda: not (target / 'letter.pdf').exists() and not window.jobs)
    (target / 'unrelated.pdf').write_bytes(pdf_bytes)
    window.delete(True)
    wait_for(app, lambda: not (target / 'unrelated.pdf').exists() and not window.jobs)
    assert not errors
    window.close()
