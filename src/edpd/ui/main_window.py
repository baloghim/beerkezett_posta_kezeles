from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass
from PySide2.QtCore import Qt, QTimer, QObject, Signal, QRunnable, QThreadPool, QByteArray
from PySide2.QtGui import QColor, QBrush, QPalette
from PySide2.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QMessageBox, QToolBar, QHeaderView,
                              QStyle, QDialog, QPushButton)
from ..config import cache_directory
from ..completion_service import CompletionStore, day_identity
from ..file_service import FileService, validate_paths
from ..models import Capabilities
from ..state_service import inventory, day_status
from ..zip_service import ZipService, read_document, MAX_PDF
from .pdf_viewer import PDFViewer
from .settings_dialog import SettingsDialog, check_settings


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


@dataclass
class Snapshot:
    days: list
    files: dict
    sizes: dict
    states: dict
    completed: set
    shared_error: str
    entries: tuple
    origins: dict
    pending: tuple
    origins_complete: bool


def row_appearance(state):
    if state == 'Elvégezve':
        return '#167235', False
    if state == 'Kicsomagolva':
        return '#000000', True
    if state == 'Részben kicsomagolva':
        return '#885000', True
    if state in ('Hibás csomag', 'Fájlütközés'):
        return '#ad2525', True
    return None, False


class MainWindow(QMainWindow):
    def __init__(self, settings, capabilities=Capabilities(), today_provider=date.today):
        super().__init__()
        self.settings, self.capabilities, self.today = settings, capabilities, today_provider
        self.zip = ZipService(cache_dir=cache_directory())
        self.days, self.files, self.sizes, self.completed = [], {}, {}, set()
        self.work_keys, self.entries, self.origin_pending = [], (), ()
        self.origins_complete, self.shared_error = True, ''
        self.jobs = set()
        self.busy = self.preview_busy = self.origin_busy = False
        self.preview_generation = self.source_generation = 0
        self.preview_pending = None
        self.setWindowTitle('EDPD 2.0 – Postai dokumentumkezelő')
        self.resize(1600, 900)
        toolbar = QToolBar('Műveletek')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.actions = []
        for title, icon, callback in [
            ('Kicsomagolás', QStyle.StandardPixmap.SP_ArrowDown, self.extract),
            ('Elvégezve jelölés', QStyle.StandardPixmap.SP_DialogApplyButton, self.toggle_done),
            ('Napi adag törlése', QStyle.StandardPixmap.SP_TrashIcon, lambda: self.delete(False)),
            ('Munkamappa ürítése', QStyle.StandardPixmap.SP_DialogDiscardButton, lambda: self.delete(True)),
            ('Frissítés', QStyle.StandardPixmap.SP_BrowserReload, self.refresh),
            ('Beállítások', QStyle.StandardPixmap.SP_FileDialogContentsView, self.configure)]:
            self.actions.append(toolbar.addAction(self.style().standardIcon(icon), title, callback))
        self.mark_action = self.actions[1]
        for action in self.actions[2:4]:
            toolbar.widgetForAction(action).setStyleSheet('color: #ad2525')
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.left = QSplitter(Qt.Orientation.Vertical)
        self.day_table = self.table(['Dátum', 'Csomag azonosítója / ZIP neve', 'PDF-ek', 'Állapot'])
        self.docs_table = self.table(['Fájlnév', 'Méret', 'Forrásnap'])
        top = self.panel('Napi csomagok (ZIP)', self.day_table)
        self.shared_notice = QLabel()
        self.shared_notice.setWordWrap(True)
        self.shared_notice.setStyleSheet('color: #ad2525; padding: 4px')
        top.layout().insertWidget(1, self.shared_notice)
        self.left.addWidget(top)
        self.left.addWidget(self.panel('A munkamappa dokumentumai', self.docs_table))
        self.viewer = PDFViewer()
        self.split.addWidget(self.left)
        self.split.addWidget(self.viewer)
        self.split.setSizes([560, 1040])
        self.setCentralWidget(self.split)
        self.day_table.itemSelectionChanged.connect(self.select_day)
        self.day_table.itemDoubleClicked.connect(self.browse_day)
        self.day_table.setToolTip('Duplakattintás: a napi ZIP-ek PDF-jeinek megtekintése kicsomagolás nélkül.')
        self.docs_table.itemSelectionChanged.connect(self.select_document)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.origin_timer = QTimer(self)
        self.origin_timer.setSingleShot(True)
        self.origin_timer.timeout.connect(self.lookup_origins)
        self.update_timer()
        for value, restore in [(settings.geometry, self.restoreGeometry), (settings.panels, self.split.restoreState), (settings.left_panels, self.left.restoreState)]:
            if value:
                restore(QByteArray.fromBase64(value.encode()))
        self.update_actions()
        QTimer.singleShot(0, self.refresh)

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        # A kijelölés minden saját sorszín fölött jól olvasható marad.
        palette = table.palette()
        for group in (QPalette.Active, QPalette.Inactive):
            palette.setColor(group, QPalette.Highlight, QColor('#245b86'))
            palette.setColor(group, QPalette.HighlightedText, QColor('white'))
        table.setPalette(palette)
        table.setStyleSheet('QTableWidget::item:selected { background: #245b86; color: white; }')
        return table

    def panel(self, title, table):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        label = QLabel(title)
        label.setStyleSheet('font-size: 16px; font-weight: 600; color: #19476b; padding: 8px')
        layout.addWidget(label)
        layout.addWidget(table)
        return panel

    def update_timer(self):
        self.timer.start(self.settings.refresh_minutes * 60_000)

    def update_actions(self):
        day = self.current_day()
        valid = day is not None and not day.error
        for action in self.actions:
            action.setEnabled(not self.busy)
        self.actions[0].setEnabled(not self.busy and valid)
        self.actions[2].setEnabled(not self.busy and valid and self.capabilities.delete)
        self.actions[3].setEnabled(not self.busy and self.capabilities.delete)
        self.mark_action.setEnabled(not self.busy and valid and not self.shared_error and self.capabilities.mark_done)
        marked = day is not None and day_identity(day) in self.completed
        self.mark_action.setText('Jelölés visszavonása' if marked else 'Elvégezve jelölés')
        self.mark_action.setToolTip(self.shared_error or 'A jelölés nem módosítja a PDF-eket.')

    def submit(self, function, success, *, kind='main', refresh_on_error=False, failure=None):
        if kind == 'main' and self.busy:
            return
        if kind == 'main':
            self.busy = True
            self.update_actions()
        job = Job(function)
        job.needs_refresh = False
        self.jobs.add(job)
        def receive(value):
            try:
                success(value)
            except Exception as exc:
                self.error(str(exc))
        def failed(text):
            job.needs_refresh = refresh_on_error
            (failure or self.error)(text)
        job.signals.done.connect(receive)
        job.signals.failed.connect(failed)
        job.signals.finished.connect(lambda: self.finish_job(job, kind))
        QThreadPool.globalInstance().start(job)

    def finish_job(self, job, kind):
        self.jobs.discard(job)
        if kind == 'main':
            self.busy = False
            self.update_actions()
            if job.needs_refresh:
                QTimer.singleShot(0, self.refresh)
        elif kind == 'preview':
            self.preview_busy = False
            if self.preview_pending:
                load, generation = self.preview_pending
                self.preview_pending = None
                QTimer.singleShot(0, lambda: self.launch_preview(load, generation))
        else:
            self.origin_busy = False
        if self.files and self.origin_pending and not self.origin_busy:
            self.origin_timer.start(250)

    def error(self, text):
        self.statusBar().showMessage('Hiba: ' + text)
        QMessageBox.warning(self, 'EDPD – Hiba', text)

    def current_day(self):
        row = self.day_table.currentRow()
        return self.days[row] if 0 <= row < len(self.days) else None

    def snapshot(self):
        settings = self.settings
        source, target = validate_paths(settings.source, settings.target)
        entries = self.zip.catalogue(source)
        days = self.zip.scan(source, settings.history_days, today=self.today(), entries=entries)
        files = inventory(target)
        sizes = {key: path.stat().st_size for key, path in files.items()}
        daily = {day.date: day_status(day, files, sizes) for day in days}
        try:
            completed = self.completion_store(settings).read()
            shared_error = ''
        except Exception as exc:
            completed, shared_error = set(), str(exc)
        origins, pending, complete = self.zip.origin_state(source, files, entries)
        return Snapshot(days, files, sizes, daily, completed, shared_error, entries, origins, pending, complete)

    def refresh(self):
        if not self.busy:
            self.statusBar().showMessage('Mappák és csomagok ellenőrzése…')
            self.submit(self.snapshot, self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        selected = self.current_day()
        self.source_generation += 1
        self.days, self.files, self.sizes = snapshot.days, snapshot.files, snapshot.sizes
        self.completed, self.shared_error = snapshot.completed, snapshot.shared_error
        self.entries, self.origin_pending = snapshot.entries, snapshot.pending
        self.origins_complete = snapshot.origins_complete
        self.shared_notice.setText(('Közös jelölések nem érhetők el: ' + self.shared_error) if self.shared_error else '')
        self.shared_notice.setVisible(bool(self.shared_error))
        self.day_table.blockSignals(True)
        self.day_table.setRowCount(len(self.days))
        row = 0
        for index, day in enumerate(self.days):
            state = 'Elvégezve' if day_identity(day) in self.completed else snapshot.states[day.date]
            display = state + (' • jelölés nem érhető el' if self.shared_error else '')
            self.fill(self.day_table, index, [day.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in day.archives), str(len(day.documents)), display])
            color, bold = row_appearance(state)
            for col in range(4):
                item = self.day_table.item(index, col)
                item.setForeground(QBrush(QColor(color) if color else self.day_table.palette().color(QPalette.Text)))
                font = item.font()
                font.setBold(bold)
                item.setFont(font)
                item.setToolTip(day.error or display)
            if selected and day.date == selected.date:
                row = index
        if self.days:
            self.day_table.selectRow(row)
        self.day_table.blockSignals(False)
        self.populate_workspace(snapshot.origins)
        self.select_day()
        self.last_refresh = datetime.now()
        self.show_status()

    def populate_workspace(self, origins):
        row = self.docs_table.currentRow()
        selected = self.work_keys[row] if 0 <= row < len(self.work_keys) else None
        self.work_keys = sorted(self.files)
        self.docs_table.blockSignals(True)
        self.docs_table.clearContents()
        self.docs_table.setRowCount(len(self.work_keys))
        self.docs_table.setCurrentCell(-1, -1)
        for row, key in enumerate(self.work_keys):
            self.fill(self.docs_table, row, [self.files[key].name, f'{self.sizes[key] / 1024:,.1f} KiB', origins.get(key, 'Ismeretlen')])
            if key == selected:
                self.docs_table.selectRow(row)
        self.docs_table.blockSignals(False)

    def show_status(self):
        progress = f'Forrásnap-index: {len(self.entries) - len(self.origin_pending)}/{len(self.entries)} ZIP'
        if not self.origins_complete and not self.origin_pending:
            progress += ' (hibás ZIP miatt hiányos)'
        self.statusBar().showMessage(f'Forrás: {self.settings.source}  |  Cél: {self.settings.target}  |  {len(self.files)} PDF  |  Frissítve: {self.last_refresh:%H:%M:%S}  |  {progress}')

    def lookup_origins(self):
        if self.busy or self.origin_busy or not self.files or not self.origin_pending:
            return
        generation, entries, source = self.source_generation, self.entries, self.settings.source
        files = dict(self.files)
        self.origin_busy = True
        batch = self.origin_pending[:8]
        def search():
            self.zip.index_batch(batch)
            labels, pending, complete = self.zip.origin_state(source, files, entries)
            if not pending:
                self.zip.save()
            return labels, pending, complete
        def found(result):
            if generation != self.source_generation:
                return
            labels, self.origin_pending, self.origins_complete = result
            for row, key in enumerate(self.work_keys):
                self.docs_table.item(row, 2).setText(labels.get(key, 'Ismeretlen'))
                self.docs_table.item(row, 2).setToolTip(labels.get(key, 'Ismeretlen'))
            self.show_status()
        def failed(text):
            if generation == self.source_generation:
                self.origin_pending = ()
                self.statusBar().showMessage('A régebbi forrásnapok keresése leállt: ' + text + ' – Frissítés után újrapróbálható.')
        self.submit(search, found, kind='origin', failure=failed)

    def fill(self, table, row, values):
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            table.setItem(row, col, item)

    def select_day(self):
        # A felső lista navigálása nem szűri a munkamappát, nem nyit új PDF-et.
        self.update_actions()

    def open_preview(self, load):
        self.preview_generation += 1
        generation = self.preview_generation
        if self.preview_busy:
            self.preview_pending = (load, generation)
        else:
            self.launch_preview(load, generation)

    def launch_preview(self, load, generation):
        if generation != self.preview_generation:
            return
        self.preview_busy = True
        self.submit(load, lambda data: self.viewer.open_data(data) if generation == self.preview_generation else None, kind='preview')

    def select_document(self):
        row = self.docs_table.currentRow()
        if not 0 <= row < len(self.work_keys):
            return
        key, target = self.work_keys[row], Path(self.settings.target)
        def load():
            files = inventory(target)
            if key not in files:
                raise ValueError('A dokumentumot időközben eltávolították. Frissítse a munkamappát!')
            with files[key].open('rb') as stream:
                data = stream.read(MAX_PDF + 1)
            if len(data) > MAX_PDF:
                raise ValueError('A PDF meghaladja a 256 MiB biztonsági korlátot.')
            return data
        self.open_preview(load)

    def open_archive_document(self, document):
        self.open_preview(lambda: read_document(document))

    def browse_day(self, *args):
        day = self.current_day()
        if not day or day.error:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f'{day.date:%Y.%m.%d.} – PDF-ek a ZIP-ben')
        dialog.resize(760, 450)
        layout = QVBoxLayout(dialog)
        table = self.table(['Fájlnév', 'Méret'])
        table.setRowCount(len(day.documents))
        for row, doc in enumerate(day.documents):
            self.fill(table, row, [doc.name, f'{doc.size / 1024:,.1f} KiB'])
        layout.addWidget(table)
        button = QPushButton('Megtekintés kicsomagolás nélkül')
        layout.addWidget(button)
        def preview(*unused):
            row = table.currentRow()
            if 0 <= row < len(day.documents):
                self.open_archive_document(day.documents[row])
                dialog.accept()
        button.clicked.connect(preview)
        table.itemDoubleClicked.connect(preview)
        dialog.exec_()

    def service(self):
        return FileService(self.settings.source, self.settings.target, self.capabilities, zip_service=self.zip)

    def completion_store(self, settings=None):
        settings = settings or self.settings
        return CompletionStore(settings.shared_data, settings.source, settings.target, self.capabilities)

    def toggle_done(self):
        day = self.current_day()
        if not day or self.shared_error or not self.capabilities.mark_done:
            return
        desired, store = day_identity(day) not in self.completed, self.completion_store()
        self.submit(lambda: (store.set_done(day, desired), self.snapshot()), self.operation_done, refresh_on_error=True)

    def extract(self):
        day = self.current_day()
        if not day or day.error:
            return
        box = QMessageBox(self)
        box.setWindowTitle('Napi csomag kicsomagolása')
        existing = sum(d.name.casefold() in self.files for d in day.documents)
        box.setText(f'A napi csomag {len(day.documents)} PDF-et tartalmaz; a legutóbbi frissítéskor {existing} már a munkamappában volt. Válasszon műveletet!')
        skip = box.addButton('Meglévők kihagyása', QMessageBox.ButtonRole.AcceptRole)
        overwrite = None
        if self.capabilities.overwrite:
            overwrite = box.addButton('Meglévők felülírása', QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton('Mégse', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip)
        box.setEscapeButton(cancel)
        box.exec_()
        if box.clickedButton() is None or box.clickedButton() not in (skip, overwrite):
            return
        mode = 'overwrite' if box.clickedButton() == overwrite else 'skip'
        service = self.service()
        self.submit(lambda: (service.extract(day, mode), self.snapshot()), self.operation_done, refresh_on_error=True)

    def delete(self, all_files):
        day = None if all_files else self.current_day()
        if not self.capabilities.delete or (not all_files and not day):
            return
        service = self.service()
        def prepare():
            return service.deletion_plan(day)
        def confirm(names):
            title = 'Teljes munkamappa ürítése' if all_files else f'{day.date:%Y.%m.%d.} napi adag törlése'
            if all_files:
                text = f'A munkamappában jelenleg {len(names)} PDF található. Biztosan törli ezt a {len(names)} PDF-et?'
            else:
                text = (f'A kiválasztott napi csomaghoz tartozó {len(day.documents)} dokumentumból jelenleg '
                        f'{len(names)} található a munkamappában. Biztosan törölni szeretné ezt a {len(names)} PDF-et?')
            if QMessageBox.question(self, title, text + '\nA törlés nem vonható vissza.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                QTimer.singleShot(0, lambda: self.submit(lambda: (service.delete(day, confirmed=True, expected_names=names), self.snapshot()), self.operation_done, refresh_on_error=True))
        self.submit(prepare, confirm)

    def operation_done(self, result):
        message, snapshot = result
        self.apply_snapshot(snapshot)
        QMessageBox.information(self, 'Művelet eredménye', message)

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            candidate = dialog.result_settings()
            def save():
                check_settings(candidate)
                candidate.save()
                return candidate
            def saved(value):
                self.settings = value
                self.preview_generation += 1
                self.source_generation += 1
                self.update_timer()
                QTimer.singleShot(0, self.refresh)
            self.submit(save, saved)

    def closeEvent(self, event):
        if self.jobs:
            QMessageBox.information(self, 'Folyamatban lévő művelet', 'Kérjük, várja meg a háttérművelet befejezését.')
            event.ignore()
            return
        self.origin_timer.stop()
        self.settings.geometry = bytes(self.saveGeometry().toBase64()).decode()
        self.settings.panels = bytes(self.split.saveState().toBase64()).decode()
        self.settings.left_panels = bytes(self.left.saveState().toBase64()).decode()
        try:
            self.zip.save()
            self.settings.save()
        except OSError as exc:
            self.error(str(exc))
            event.ignore()
            return
        if self.viewer.pdf:
            self.viewer.pdf.close()
        event.accept()
