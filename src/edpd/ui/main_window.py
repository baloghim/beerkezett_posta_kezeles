from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass
from PySide2.QtCore import Qt, QTimer, QObject, Signal, QRunnable, QThreadPool, QByteArray
from PySide2.QtGui import QColor, QBrush, QPalette
from .. import __version__
from PySide2.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QMessageBox, QToolBar, QHeaderView,
                              QStyle, QDialog, QPushButton, QAction, QSizePolicy, QToolButton)
from ..config import cache_directory
from ..completion_service import CompletionStore, day_identity
from ..file_service import FileService, validate_paths
from ..models import Capabilities
from ..paths import directory
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


@dataclass(frozen=True)
class DailyArchiveModel:
    days: list
    states: dict
    entries: tuple


@dataclass(frozen=True)
class WorkspaceModel:
    files: dict
    sizes: dict
    origins: dict


@dataclass(frozen=True)
class Snapshot:
    archive: DailyArchiveModel
    workspace: WorkspaceModel
    completed: set
    shared_error: str
    pending: tuple
    origins_complete: bool
    access_error: str = ''


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
        self.origins_complete, self.shared_error, self.access_error = True, '', ''
        self.archive_model = DailyArchiveModel([], {}, ())
        self.workspace_model = WorkspaceModel({}, {}, {})
        self.origin_requested = False
        self.jobs = set()
        self.busy = self.preview_busy = self.origin_busy = False
        self.preview_generation = self.source_generation = 0
        self.preview_pending = None
        self.setWindowTitle(f'EDPD {__version__} – Postai dokumentumkezelő')
        self.resize(1600, 900)
        toolbar = QToolBar('Műveletek')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.actions = []
        for title, icon, callback in [
            ('Kicsomagolás', QStyle.StandardPixmap.SP_ArrowDown, self.extract),
            ('Elvégezve jelölés', QStyle.StandardPixmap.SP_DialogApplyButton, self.toggle_done),
            ('Kijelölt nap fájljainak törlése', QStyle.StandardPixmap.SP_TrashIcon, lambda: self.delete(False)),
            ('Munkamappa ürítése', QStyle.StandardPixmap.SP_DialogDiscardButton, lambda: self.delete(True)),
            ('Frissítés', QStyle.StandardPixmap.SP_BrowserReload, self.refresh),
            ('Beállítások', QStyle.StandardPixmap.SP_FileDialogContentsView, self.configure)]:
            self.actions.append(toolbar.addAction(self.style().standardIcon(icon), title, callback))
        self.mark_action = self.actions[1]
        self.main_toolbar = toolbar
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        self.about_button = QToolButton()
        self.about_button.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.about_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.about_button.setToolTip('Névjegy')
        self.about_button.setAccessibleName('Névjegy')
        self.about_button.clicked.connect(self.show_about)
        toolbar.addWidget(self.about_button)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.left = QSplitter(Qt.Orientation.Vertical)
        self.day_table = self.table(['Dátum', 'Csomag azonosítója / ZIP neve', 'PDF-ek', 'Állapot'])
        self.docs_table = self.table(['Fájlnév', 'Méret', 'Forrásnap'])
        self.docs_table.horizontalHeaderItem(2).setToolTip('Az ismert, friss ZIP-tartalomjegyzékek alapján. Régebbi feltérképezés csak a További forráskeresés gombbal.')
        self.docs_table.horizontalHeader().setStretchLastSection(False)
        self.docs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.docs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.docs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        top = self.panel('EDPD mappa tartalma', self.day_table)
        self.shared_notice = QLabel()
        self.shared_notice.setWordWrap(True)
        top.layout().insertWidget(1, self.shared_notice)
        self.left.addWidget(top)
        self.workspace_panel = self.panel('A munkamappa dokumentumai', self.docs_table)
        self.origin_button = QPushButton('További forráskeresés')
        self.origin_button.setToolTip('Csak külön kérésre nyitjuk meg a még nem ismert régebbi ZIP-eket.')
        self.origin_button.clicked.connect(self.request_origin_search)
        self.workspace_panel.layout().insertWidget(1, self.origin_button)
        self.left.addWidget(self.workspace_panel)
        self.viewer = PDFViewer()
        self.split.addWidget(self.left)
        self.split.addWidget(self.viewer)
        self.split.setSizes([560, 1040])
        self.setCentralWidget(self.split)
        self.day_table.itemSelectionChanged.connect(self.select_day)
        self.day_table.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.archive_preview_action = QAction('ZIP-csomag PDF-jeinek megtekintése…', self.day_table)
        self.archive_preview_action.triggered.connect(self.browse_day)
        self.day_table.addAction(self.archive_preview_action)
        self.day_table.setToolTip('Jobb kattintás: ZIP-betekintés. A nap kiválasztása nem változtatja a munkamappa-listát.')
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
        return table

    def panel(self, title, table):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        label = QLabel(title)
        panel.title_label = label
        layout.addWidget(label)
        layout.addWidget(table)
        return panel

    def update_timer(self):
        self.timer.start(self.settings.refresh_minutes * 60_000)

    def update_actions(self):
        day = self.current_day()
        valid = day is not None and not day.error and not self.access_error
        for action in self.actions:
            action.setEnabled(not self.busy)
        self.actions[0].setEnabled(not self.busy and valid)
        self.actions[2].setEnabled(not self.busy and valid and self.capabilities.delete)
        self.actions[3].setEnabled(not self.busy and self.capabilities.delete and not self.access_error)
        self.mark_action.setEnabled(not self.busy and valid and not self.shared_error and self.capabilities.mark_done)
        marked = day is not None and day_identity(day) in self.completed
        self.mark_action.setText('Jelölés visszavonása' if marked else 'Elvégezve jelölés')
        self.mark_action.setToolTip(self.shared_error or 'A jelölés nem módosítja a PDF-eket.')
        self.update_origin_button()

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
        if self.origin_requested and self.files and self.origin_pending and not self.origin_busy:
            self.origin_timer.start(250)

    def error(self, text):
        self.statusBar().showMessage('Hiba: ' + text)
        QMessageBox.warning(self, 'EDPD – Hiba', text)

    def current_day(self):
        row = self.day_table.currentRow()
        return self.days[row] if 0 <= row < len(self.days) else None

    def read_workspace(self, settings):
        try:
            target = directory(settings.target, 'A munkamappa')
            files = inventory(target)
            sizes = {key: path.stat().st_size for key, path in files.items()}
            return WorkspaceModel(files, sizes, {}), target, ''
        except Exception as exc:
            return WorkspaceModel({}, {}, {}), None, 'A munkamappa nem olvasható: ' + str(exc)

    def read_daily_archives(self, settings):
        try:
            source = directory(settings.source, 'A forrásarchívum')
            entries = self.zip.catalogue(source)
            days = self.zip.scan(source, settings.history_days, today=self.today(), entries=entries)
            return DailyArchiveModel(days, {}, entries), source, ''
        except Exception as exc:
            return DailyArchiveModel([], {}, ()), None, str(exc)

    def snapshot(self):
        settings = self.settings
        source_error = target_error = guard_error = ''
        source = target = None
        days, entries, files, sizes = [], (), {}, {}
        workspace, target, target_error = self.read_workspace(settings)
        files, sizes = workspace.files, workspace.sizes
        archive, source, source_error = self.read_daily_archives(settings)
        days, entries = archive.days, archive.entries
        if source is not None and target is not None:
            try:
                validate_paths(source, target)
            except Exception as exc:
                guard_error = str(exc)
        access_error = '\n'.join(e for e in (source_error, target_error, guard_error) if e)
        daily = {day.date: ('Munkamappa nem érhető el' if target_error else day_status(day, files, sizes)) for day in days}
        try:
            completed = self.completion_store(settings).read()
            shared_error = ''
        except Exception as exc:
            completed, shared_error = set(), str(exc)
        if source_error:
            origins, pending, complete = {name: 'Ismeretlen' for name in files}, (), False
        else:
            origins, pending, complete = self.zip.origin_state(source, files, entries)
        return Snapshot(DailyArchiveModel(days, daily, entries), WorkspaceModel(files, sizes, origins), completed, shared_error, pending, complete, access_error)

    def refresh(self):
        if not self.busy:
            self.statusBar().showMessage('Mappák és csomagok ellenőrzése…')
            self.submit(self.snapshot, self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        selected = self.current_day()
        self.source_generation += 1
        self.archive_model, self.workspace_model = snapshot.archive, snapshot.workspace
        self.days, self.files, self.sizes = snapshot.archive.days, snapshot.workspace.files, snapshot.workspace.sizes
        self.completed, self.shared_error, self.access_error = snapshot.completed, snapshot.shared_error, snapshot.access_error
        self.entries, self.origin_pending = snapshot.archive.entries, snapshot.pending
        self.origins_complete = snapshot.origins_complete
        if not self.origin_pending:
            self.origin_requested = False
        notice = self.access_error or (('Közös jelölések nem érhetők el: ' + self.shared_error) if self.shared_error else '')
        self.shared_notice.setText(notice)
        self.shared_notice.setVisible(bool(notice))
        self.day_table.blockSignals(True)
        self.day_table.setUpdatesEnabled(False)
        header = self.day_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.day_table.setRowCount(len(self.days))
        row = 0
        for index, day in enumerate(self.days):
            state = 'Elvégezve' if day_identity(day) in self.completed else snapshot.archive.states[day.date]
            display = state + (' • jelölés nem érhető el' if self.shared_error else '')
            color, bold = row_appearance(state)
            self.fill(self.day_table, index,
                      [day.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in day.archives), str(len(day.documents)), display],
                      appearance=(color, bold), tooltip=day.error or display)
            if selected and day.date == selected.date:
                row = index
        if self.days:
            self.day_table.selectRow(row)
        header.setResizeContentsPrecision(64)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.day_table.setUpdatesEnabled(True)
        self.day_table.blockSignals(False)
        self.populate_workspace(snapshot.workspace.origins)
        self.select_day()
        self.last_refresh = datetime.now()
        self.show_status()

    def populate_workspace(self, origins):
        row = self.docs_table.currentRow()
        selected = self.work_keys[row] if 0 <= row < len(self.work_keys) else None
        self.work_keys = sorted(self.files)
        self.docs_table.blockSignals(True)
        self.docs_table.setUpdatesEnabled(False)
        self.docs_table.clearContents()
        self.docs_table.setRowCount(len(self.work_keys))
        self.docs_table.setCurrentCell(-1, -1)
        for row, key in enumerate(self.work_keys):
            self.fill(self.docs_table, row, [self.files[key].name, f'{self.sizes[key] / 1024:,.1f} KiB', origins.get(key, 'Ismeretlen')])
            if key == selected:
                self.docs_table.selectRow(row)
        self.docs_table.setUpdatesEnabled(True)
        self.docs_table.blockSignals(False)

    def show_status(self):
        progress = f'Forrásnap-index: {len(self.entries) - len(self.origin_pending)}/{len(self.entries)} ZIP'
        if not self.origins_complete and not self.origin_pending:
            progress += ' (elérési hiba miatt hiányos)' if self.access_error else ' (hibás ZIP miatt hiányos)'
        period = f'{self.settings.history_days} nap' if self.settings.history_days is not None else 'Összes'
        progress += ' • kézi keresés folyamatban' if self.origin_requested else ' • további keresés csak kérésre'
        self.statusBar().showMessage(f'v{__version__}  |  Időszak: {period}  |  Forrás: {self.settings.source}  |  Cél: {self.settings.target}  |  {len(self.files)} PDF  |  Frissítve: {self.last_refresh:%H:%M:%S}  |  {progress}')

    def update_origin_button(self):
        self.origin_button.setText('Keresés szüneteltetése' if self.origin_requested else f'További forráskeresés ({len(self.origin_pending)} ZIP)')
        self.origin_button.setEnabled(not self.busy and bool(self.files) and bool(self.origin_pending) and not self.access_error)

    def request_origin_search(self):
        if self.busy or self.access_error or not self.files or not self.origin_pending:
            return
        self.origin_requested = not self.origin_requested
        if self.origin_requested:
            self.origin_timer.start(0)
        else:
            self.origin_timer.stop()
        self.update_origin_button()
        self.show_status()

    def lookup_origins(self):
        if not self.origin_requested or self.busy or self.origin_busy or not self.files or not self.origin_pending:
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
            self.workspace_model = WorkspaceModel(self.files, self.sizes, labels)
            if not self.origin_pending:
                self.origin_requested = False
            self.update_origin_button()
            for row, key in enumerate(self.work_keys):
                self.docs_table.item(row, 2).setText(labels.get(key, 'Ismeretlen'))
                self.docs_table.item(row, 2).setToolTip(labels.get(key, 'Ismeretlen'))
            self.show_status()
        def failed(text):
            if generation == self.source_generation:
                self.origin_pending = ()
                self.origin_requested = False
                self.update_origin_button()
                self.statusBar().showMessage('A régebbi forrásnapok keresése leállt: ' + text + ' – Frissítés után újrapróbálható.')
        self.submit(search, found, kind='origin', failure=failed)

    def fill(self, table, row, values, appearance=None, tooltip=None):
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(tooltip or value)
            if appearance is not None:
                color, bold = appearance
                item.setForeground(QBrush(QColor(color) if color else table.palette().color(QPalette.Text)))
                font = item.font()
                font.setBold(bold)
                item.setFont(font)
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
        return CompletionStore(settings.shared_data, settings.source, settings.target, self.capabilities, zip_service=self.zip)

    def toggle_done(self):
        day = self.current_day()
        if not day or self.shared_error or self.access_error or not self.capabilities.mark_done:
            return
        desired, store = day_identity(day) not in self.completed, self.completion_store()
        self.submit(lambda: (store.set_done(day, desired), self.snapshot()), self.operation_done, refresh_on_error=True)

    def extract(self):
        day = self.current_day()
        if not day or day.error or self.access_error:
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
        if self.access_error or not self.capabilities.delete or (not all_files and not day):
            return
        service = self.service()
        def prepare():
            return service.deletion_plan(day)
        def confirm(names):
            title = 'Teljes munkamappa ürítése' if all_files else 'Kijelölt nap fájljainak törlése'
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

    def show_about(self):
        from .about_dialog import AboutDialog
        AboutDialog(self).exec_()

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            candidate = dialog.result_settings()
            def save():
                check_settings(candidate)
                candidate.save()
                return candidate
            def saved(value):
                self.origin_requested = False
                self.origin_timer.stop()
                self.settings = value
                from .appearance import apply_style
                apply_style(value.qt_style)
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
