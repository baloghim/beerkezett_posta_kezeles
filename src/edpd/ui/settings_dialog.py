from dataclasses import replace
import tempfile
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
                              QDialogButtonBox, QHBoxLayout, QFileDialog, QSlider, QLabel, QStyleFactory, QGroupBox, QApplication)
from ..file_service import validate_paths
from ..paths import normalize_path
from .icons import THEME_NAMES
from .themes import THEME_NAMES as SURFACE_THEMES
from .appearance import current_style_name
from .themes.widgets import SurfaceComboBox as QComboBox


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
        self.history = QComboBox()
        for days in (14, 30, 90, 180, None):
            self.history.addItem(f'{days} nap' if days is not None else 'Összes', days)
        self.history.setCurrentIndex(self.history.findData(settings.history_days))
        form.addRow('Napi ZIP-lista időszaka', self.history)
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
        layout.addWidget(QLabel('Mappaváltoztatáskor háttérben ellenőrizzük az útvonalakat és az írási jogosultságot.'))
        appearance = QGroupBox('Megjelenés')
        appearance_form = QFormLayout(appearance)
        self.style_combo = QComboBox()
        for key in QStyleFactory.keys():
            self.style_combo.addItem('Vista' if key.lower() == 'windowsvista' else key, key)
        current = current_style_name()
        selected = next((i for i in range(self.style_combo.count())
                         if self.style_combo.itemData(i).lower() == current.lower()), 0)
        self.style_combo.setCurrentIndex(selected)
        appearance_form.addRow('Qt-stílus', self.style_combo)
        self.surface_combo = QComboBox()
        self.surface_combo.addItems(SURFACE_THEMES)
        self.surface_combo.setCurrentText(settings.surface_theme if settings.surface_theme in SURFACE_THEMES else SURFACE_THEMES[0])
        appearance_form.addRow('Felületi téma', self.surface_combo)
        self.icon_combo = QComboBox()
        self.icon_combo.addItems(THEME_NAMES)
        self.icon_combo.setCurrentText(settings.icon_theme if settings.icon_theme in THEME_NAMES else 'Crystal SVG')
        appearance_form.addRow('Ikontéma', self.icon_combo)
        layout.addWidget(appearance)
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
        return replace(self.original, source=normalize_path(self.source.text()), target=normalize_path(self.target.text()),
                       history_days=self.history.currentData(),
                       refresh_minutes=self.slider.value() * 5, qt_style=self.style_combo.currentData(), icon_theme=self.icon_combo.currentText(),
                       surface_theme=self.surface_combo.currentText())


def check_settings(settings):
    source, target = validate_paths(settings.source, settings.target)
    # Forrásban soha nem végzünk próbaírást.
    with __import__('os').scandir(source) as entries:
        next(entries, None)
    with tempfile.TemporaryFile(dir=target) as stream:
        stream.write(b'EDPD')
        stream.flush()
    return settings
