from ..qt_image import image_from_pixmap
from PySide2.QtCore import Qt, QSize, QEvent, QTimer
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QWidget, QVBoxLayout, QToolBar, QScrollArea, QLabel, QMessageBox
from .icons import icon
from ..pdf_service import PDFService
from ..print_service import print_pdf


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.pdf = None
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

    def open_data(self, data):
        pdf = PDFService(data)
        if self.pdf:
            self.pdf.close()
        self.pdf = pdf
        self.page = 0
        self.fit_mode = 'width'
        self.print_action.setEnabled(True)
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
