from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from .icons import icon, manager


class ExtractionDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, day, parent):
        super().__init__(parent)
        self.setWindowTitle('Napi csomag kicsomagolása')
        self.setWindowIcon(icon('extract'))
        self.setWindowModality(Qt.WindowModal)
        self.setModal(True)
        self.resize(480, 220)
        self.finished_operation = False
        self.cancel_pending = False
        layout = QVBoxLayout(self)
        self.image = QLabel()
        self.image.setPixmap(icon('extract').pixmap(40, 40))
        layout.addWidget(self.image)
        layout.addWidget(QLabel(f'{day.date:%Y.%m.%d.} napi dokumentumok kicsomagolása'))
        self.label = QLabel('Kicsomagolás előkészítése…')
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)
        self.cancel_button = QPushButton('Mégse')
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        manager().subscribe(self)

    def update_progress(self, text, done, total):
        if not self.cancel_pending or 'visszaállítás' in text.lower():
            self.label.setText(f'{text}: {done} / {total}' if total else text)
        self.bar.setRange(0, total)
        self.bar.setValue(done)

    def reject(self):
        if not self.finished_operation and not self.cancel_pending:
            self.cancel_pending = True
            self.cancel_button.setEnabled(False)
            self.label.setText('Megszakítás és visszaállítás kérése…')
            self.cancel_requested.emit()

    def closeEvent(self, event):
        if self.finished_operation:
            event.accept()
        else:
            self.reject()
            event.ignore()

    def complete(self, success=True):
        self.finished_operation = True
        if success and not self.cancel_pending:
            self.bar.setRange(0, 100)
            self.bar.setValue(100)
        self.accept()

    def refresh_icons(self):
        self.setWindowIcon(icon('extract'))
        self.image.setPixmap(icon('extract').pixmap(40,40))
