from ..qt_image import image_from_pixmap
from PySide2.QtCore import Qt, QSize, QEvent, QTimer, QObject, Signal, QRunnable, QThreadPool
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QWidget, QVBoxLayout, QToolBar, QScrollArea, QLabel, QMessageBox, QFileDialog
from .icons import icon
from ..pdf_service import PDFService
from ..print_service import print_pdf
from ..pdf_export import save_pdf, validate_export, target_stamp
from pathlib import Path


class SaveSignals(QObject):
    done = Signal(str)
    failed = Signal(str)
    finished = Signal()


class SaveWorker(QRunnable):
    def __init__(self, data, path, source, target, expected, protected):
        super().__init__()
        self.arguments = data, path, source, target, expected, protected
        self.signals = SaveSignals()

    def run(self):
        try:
            save_pdf(*self.arguments)
            self.signals.done.emit(str(self.arguments[1]))
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class PDFViewer(QWidget):
    saved = Signal(str)

    def __init__(self):
        super().__init__()
        self.pdf = None
        self.filename = 'dokumentum.pdf'
        self.source_path = self.workspace_path = None
        self.save_job = None
        self.document_folders = ()
        self.page = 0
        self.scale = 1.0
        self.fit_mode = 'width'
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar('PDF')
        self.toolbar.setIconSize(QSize(22, 22))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        layout.addWidget(self.toolbar)
        for name, title, callback in [('first', 'Első oldal', lambda: self.move(0)),
                                      ('previous', 'Előző oldal', lambda: self.move(self.page - 1)),
                                      ('next', 'Következő oldal', lambda: self.move(self.page + 1)),
                                      ('last', 'Utolsó oldal', lambda: self.move(self.pdf.pages - 1) if self.pdf else None)]:
            self.toolbar.addAction(icon(name), title, callback)
        self.page_label = QLabel('Nincs megnyitott PDF')
        self.toolbar.addWidget(self.page_label)
        self.toolbar.addAction(icon('zoom_out'), 'Kicsinyítés', lambda: self.zoom(0.8))
        self.toolbar.addAction(icon('zoom_in'), 'Nagyítás', lambda: self.zoom(1.25))
        self.width_action = self.toolbar.addAction(icon('width'), 'Szélesség', lambda: self.fit('width'))
        self.width_action.setToolTip('Az oldal igazítása a betekintő szélességéhez')
        self.page_action = self.toolbar.addAction(icon('page'), 'Teljes oldal', lambda: self.fit('page'))
        self.page_action.setToolTip('A teljes oldal igazítása a látható területhez')
        for action in (self.width_action, self.page_action):
            action.setCheckable(True)
        self.print_action = self.toolbar.addAction(icon('print'), 'Nyomtatás', self.print_current)
        self.print_action.setEnabled(False)
        self.save_action = self.toolbar.addAction(icon('save'), 'PDF mentése', self.save_current)
        self.save_action.setEnabled(False)
        for action in (self.width_action, self.page_action, self.print_action, self.save_action):
            self.toolbar.widgetForAction(action).setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel('Válasszon egy dokumentumot a betekintéshez.')
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.label)
        self.scroll.viewport().installEventFilter(self)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.render)
        layout.addWidget(self.scroll)

    def open_data(self, data, filename='dokumentum.pdf'):
        pdf = PDFService(data)
        self.filename = Path(filename).name
        self.document_folders = tuple(p for p in (self.source_path, self.workspace_path) if p)
        if self.pdf:
            self.pdf.close()
        self.pdf = pdf
        self.page = 0
        self.fit_mode = 'width'
        self.print_action.setEnabled(True)
        self.save_action.setEnabled(self.save_job is None)
        self.render()

    def move(self, page):
        if self.pdf:
            self.page = min(max(0, page), self.pdf.pages - 1)
            self.render()

    def zoom(self, factor):
        self.fit_mode = None
        self.scale = min(5, max(0.1, self.scale * factor))
        self.render()

    def fit(self, mode):
        self.fit_mode = mode
        self.render()

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize and self.fit_mode:
            self.fit_timer.start(0)
        return super().eventFilter(watched, event)

    def render(self):
        self.width_action.setChecked(self.fit_mode == 'width')
        self.page_action.setChecked(self.fit_mode == 'page')
        if not self.pdf or self.pdf.document.is_closed:
            return
        try:
            if self.fit_mode:
                rect = self.pdf.document[self.page].rect
                width = max(100, self.scroll.viewport().width() - 24)
                height = max(100, self.scroll.viewport().height() - 24)
                self.scale = width / rect.width
                if self.fit_mode == 'page':
                    self.scale = min(self.scale, height / rect.height)
            pix = self.pdf.render(self.page, self.scale)
            image = image_from_pixmap(pix)
            self.label.setPixmap(QPixmap.fromImage(image))
            self.label.resize(pix.width, pix.height)
            self.page_label.setText(f'  {self.page + 1} / {self.pdf.pages}  ')
        except Exception as exc:
            QMessageBox.warning(self, 'PDF-megjelenítési hiba', str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode:
            self.fit_timer.start(0)

    def hideEvent(self, event):
        self.fit_timer.stop()
        super().hideEvent(event)

    def print_current(self):
        if self.pdf:
            try:
                print_pdf(self.pdf, self)
            except Exception as exc:
                QMessageBox.warning(self, 'Nyomtatási hiba', str(exc))

    def set_paths(self, source, target):
        self.source_path, self.workspace_path = source, target

    def save_current(self):
        if not self.pdf or self.pdf.document.is_closed or self.save_job is not None:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'PDF mentése', self.filename,
                                             'PDF-dokumentum (*.pdf)', options=QFileDialog.DontConfirmOverwrite)
        if not path:
            return
        try:
            path = validate_export(path, self.source_path, self.workspace_path)
            for folder in self.document_folders:
                validate_export(path, folder)
            expected = target_stamp(path)
            if expected is not None and QMessageBox.question(self, 'PDF felülírása',
                    f'A fájl már létezik: {path.name}\nFelülírja?', QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return
            job = SaveWorker(self.pdf.data, path, self.source_path, self.workspace_path, expected, self.document_folders)
            self.save_job = job
            self.save_action.setEnabled(False)
            job.signals.done.connect(self.saved.emit)
            job.signals.failed.connect(lambda text: QMessageBox.warning(self, 'PDF mentési hiba', text))
            def finished():
                self.save_job = None
                self.save_action.setEnabled(self.pdf is not None and not self.pdf.document.is_closed)
            job.signals.finished.connect(finished)
            QThreadPool.globalInstance().start(job)
        except Exception as exc:
            QMessageBox.warning(self, 'PDF mentési hiba', str(exc))
