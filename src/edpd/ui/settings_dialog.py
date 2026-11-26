from dataclasses import replace
import tempfile
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QCheckBox,
                              QDialogButtonBox, QHBoxLayout, QFileDialog, QSlider, QLabel, QStyleFactory, QGroupBox, QApplication)
from ..file_service import validate_paths
from ..paths import normalize_path
from ..pdf_export import documents_directory
from .icons import THEME_NAMES
from .appearance import ui_style_choices, resolve_ui_style
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
        def add_path_row(title, edit):
            row = QHBoxLayout()
            row.addWidget(edit)
            browse = QPushButton('Tallózás…')
            browse.clicked.connect(lambda checked=False, e=edit: self.browse(e))
            row.addWidget(browse)
            form.addRow(title, row)

        self.source = QLineEdit(settings.source)
        self.viewer_mode = not hasattr(settings, 'target')
        add_path_row('Forrásarchívum (csak olvasás)', self.source)
        if not self.viewer_mode:
            self.target = QLineEdit(settings.target)
            add_path_row('Ideiglenes munkamappa', self.target)
            self.shared_workspace = QCheckBox('Ez egy közös mappa')
            self.shared_workspace.setChecked(settings.shared_workspace)
            explanation = QLabel('A feldolgozottsági jelzőket az ezt a munkamappát használó '
                                 'munkatársak közösen látják és módosítják.')
            explanation.setWordWrap(True)
            shared = QVBoxLayout()
            shared.addWidget(self.shared_workspace)
            shared.addWidget(explanation)
            form.addRow('', shared)
        self.initial_pdf_save_dir = settings.default_pdf_save_dir or documents_directory()
        self.pdf_save_dir = QLineEdit(self.initial_pdf_save_dir)
        self.pdf_save_dir.setPlaceholderText('Dokumentumok')
        add_path_row('Alapértelmezett PDF-mentési mappa', self.pdf_save_dir)
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
        layout.addWidget(QLabel('A forrásarchívum olvashatóságát ellenőrizzük.' if self.viewer_mode else
                                'Mappaváltoztatáskor háttérben ellenőrizzük az útvonalakat és az írási jogosultságot.'))
        appearance = QGroupBox('Megjelenés')
        appearance_form = QFormLayout(appearance)
        self.style_combo = QComboBox()
        for label, key in ui_style_choices():
            self.style_combo.addItem(label, key)
        current = resolve_ui_style(settings.ui_style)[0]
        self.style_combo.setCurrentIndex(self.style_combo.findData(current))
        appearance_form.addRow('Felületi stílus', self.style_combo)
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
            edit.setModified(True)

    def result_settings(self):
        ui_style, qt_style, surface = resolve_ui_style(self.style_combo.currentData())
        paths = {} if self.viewer_mode else {
            'target': normalize_path(self.target.text()),
            'shared_workspace': self.shared_workspace.isChecked(),
        }
        pdf_save_dir = normalize_path(self.pdf_save_dir.text())
        if (not self.original.default_pdf_save_dir and not self.pdf_save_dir.isModified()
                and self.pdf_save_dir.text() == self.initial_pdf_save_dir):
            pdf_save_dir = ''
        return replace(self.original, source=normalize_path(self.source.text()), **paths,
                       default_pdf_save_dir=pdf_save_dir,
                       history_days=self.history.currentData(),
                       refresh_minutes=self.slider.value() * 5, qt_style=qt_style, icon_theme=self.icon_combo.currentText(),
                       surface_theme=surface, ui_style=ui_style)


def check_settings(settings):
    source, target = validate_paths(settings.source, settings.target)
    # Forrásban soha nem végzünk próbaírást.
    with __import__('os').scandir(source) as entries:
        next(entries, None)
    with tempfile.TemporaryFile(dir=target) as stream:
        stream.write(b'EDPD')
        stream.flush()
    return settings
