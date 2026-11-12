from dataclasses import replace
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
                              QDialogButtonBox, QHBoxLayout, QFileDialog, QSlider, QLabel)
from ..file_service import validate_paths


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.original = settings
        self.setWindowTitle('Beállítások')
        self.resize(760, 250)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.source = QLineEdit(settings.source)
        self.target = QLineEdit(settings.target)
        for title, edit in [('Forrásarchívum (csak olvasás)', self.source), ('Ideiglenes munkamappa', self.target)]:
            row = QHBoxLayout()
            row.addWidget(edit)
            browse = QPushButton('Tallózás…')
            browse.clicked.connect(lambda checked=False, e=edit: self.browse(e))
            row.addWidget(browse)
            form.addRow(title, row)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 12)
        self.slider.setValue(settings.refresh_minutes // 5)
        self.value = QLabel()
        self.slider.valueChanged.connect(self.update_label)
        self.update_label()
        row = QHBoxLayout()
        row.addWidget(self.slider)
        row.addWidget(self.value)
        reset = QPushButton('Alapérték (15 perc)')
        reset.clicked.connect(lambda: self.slider.setValue(3))
        row.addWidget(reset)
        form.addRow('Automatikus frissítés', row)
        layout.addWidget(QLabel('Mentéskor háttérben ellenőrizzük az elérhetőséget és a cél írási jogosultságát.'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Mentés')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Mégse')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_label(self):
        self.value.setText(f'{self.slider.value() * 5} perc')

    def browse(self, edit):
        path = QFileDialog.getExistingDirectory(self, 'Mappa kiválasztása', edit.text())
        if path:
            edit.setText(path)

    def result_settings(self):
        return replace(self.original, source=self.source.text().strip(), target=self.target.text().strip(), refresh_minutes=self.slider.value() * 5)


def check_settings(settings):
    source, target = validate_paths(settings.source, settings.target)
    # Forrásban soha nem végzünk próbaírást.
    with __import__('os').scandir(source) as entries:
        next(entries, None)
    with tempfile.TemporaryFile(dir=target) as stream:
        stream.write(b'EDPD')
        stream.flush()
    return settings
