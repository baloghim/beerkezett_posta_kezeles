from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolBar, QScrollArea, QLabel, QMessageBox, QStyle
from ..pdf_service import PDFService
from ..print_service import print_pdf


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.pdf = None
        self.page = 0
        self.scale = 1.0
        self.fit_mode = 'page'
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar('PDF')
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.toolbar)
        for title, callback in [('⏮', lambda: self.move(0)), ('◀', lambda: self.move(self.page - 1)),
                                ('▶', lambda: self.move(self.page + 1)), ('⏭', lambda: self.move(self.pdf.pages - 1) if self.pdf else None)]:
            self.toolbar.addAction(title, callback)
        self.page_label = QLabel('Nincs megnyitott PDF')
        self.toolbar.addWidget(self.page_label)
        self.toolbar.addAction('−', lambda: self.zoom(0.8))
        self.toolbar.addAction('+', lambda: self.zoom(1.25))
        self.toolbar.addAction('Szélesség', lambda: self.fit('width'))
        self.toolbar.addAction('Teljes oldal', lambda: self.fit('page'))
        self.print_action = self.toolbar.addAction(printer_icon(), 'Nyomtatás', self.print_current)
        self.print_action.setEnabled(False)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel('Válasszon egy dokumentumot a betekintéshez.')
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)

    def open_data(self, data):
        pdf = PDFService(data)
        if self.pdf:
            self.pdf.close()
        self.pdf = pdf
        self.page = 0
        self.fit_mode = 'page'
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

    def render(self):
        if not self.pdf:
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
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
            self.label.setPixmap(QPixmap.fromImage(image))
            self.label.resize(pix.width, pix.height)
            self.page_label.setText(f'  {self.page + 1} / {self.pdf.pages}  ')
        except Exception as exc:
            QMessageBox.warning(self, 'PDF-megjelenítési hiba', str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode:
            self.render()

    def print_current(self):
        if self.pdf:
            try:
                print_pdf(self.pdf, self)
            except Exception as exc:
                QMessageBox.warning(self, 'Nyomtatási hiba', str(exc))


def printer_icon():
    pix = QPixmap(24, 24)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#29445d'), 1.5))
    painter.setBrush(QColor('white'))
    painter.drawRect(6, 2, 12, 8)
    painter.setBrush(QColor('#b8cbd9'))
    painter.drawRoundedRect(2, 8, 20, 11, 2, 2)
    painter.setBrush(QColor('white'))
    painter.drawRect(6, 13, 12, 9)
    painter.drawLine(9, 16, 15, 16)
    painter.drawLine(9, 19, 15, 19)
    painter.end()
    return QIcon(pix)
