from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass
from PySide2.QtCore import Qt, QTimer, QObject, Signal, QSize, QRunnable, QThreadPool, QByteArray
from PySide2.QtGui import QColor, QBrush, QPalette
from .. import __version__
from PySide2.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QMessageBox, QToolBar, QHeaderView,
                              QDialog, QPushButton, QAction, QSizePolicy, QToolButton, QHBoxLayout, QProgressBar)
from ..config import cache_directory
from ..file_service import FileService, validate_paths
from ..models import Capabilities
from ..paths import directory
from ..state_service import inventory, day_status
from ..zip_service import ZipService, read_document, MAX_PDF
from .pdf_viewer import PDFViewer
from .icons import icon
from .settings_dialog import SettingsDialog, check_settings


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()
    progress = Signal(str, int, int)


class Job(QRunnable):
    def __init__(self, function, with_progress=False):
        super().__init__()
        self.function = function
        self.with_progress = with_progress
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function(self.signals.progress.emit) if self.with_progress else self.function())
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
    pending: tuple
    origins_complete: bool
    access_error: str = ''


def row_appearance(state):
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
        self.days, self.files, self.sizes = [], {}, {}
        self.work_keys, self.entries, self.origin_pending = [], (), ()
        self.origins_complete, self.access_error = True, ''
        self.archive_model = DailyArchiveModel([], {}, ())
        self.workspace_model = WorkspaceModel({}, {}, {})
        self.origin_requested = False
        self.jobs = set()
        self.busy = self.preview_busy = self.origin_busy = False
        self.preview_generation = self.source_generation = 0
        self.preview_pending = None
        self.extracting = False
        self.extraction_label = QLabel()
        self.extraction_bar = QProgressBar()
        self.extraction_bar.setMaximumWidth(220)
        self.statusBar().addPermanentWidget(self.extraction_label)
        self.statusBar().addPermanentWidget(self.extraction_bar)
        self.extraction_label.hide()
        self.extraction_bar.hide()
        self.setWindowTitle(f'EDPD {__version__} – Postai dokumentumkezelő')
        self.setWindowIcon(icon('app'))
        self.resize(1600, 900)
        toolbar = QToolBar('Műveletek')
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.main_toolbar = toolbar
        self.toolbar_controls = QWidget()
        self.toolbar_controls.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_layout = QHBoxLayout(self.toolbar_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self.toolbar_controls)
        # Only operation buttons may overflow; About always keeps its own space.
        toolbar = QToolBar('Műveleti gombok')
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        controls_layout.addWidget(toolbar, 1)
        self.actions = []
        for title, icon_name, callback in [
            ('Kicsomagolás', 'extract', self.extract),
            ('Kijelölt nap fájljainak törlése', 'delete', lambda: self.delete(False)),
            ('Munkamappa ürítése', 'clear', lambda: self.delete(True)),
            ('Frissítés', 'refresh', self.refresh),
            ('Beállítások', 'settings', self.configure)]:
            self.actions.append(toolbar.addAction(icon(icon_name), title, callback))
        self.about_button = QToolButton()
        self.about_button.setIcon(icon('about'))
        self.about_button.setIconSize(QSize(32, 32))
        self.about_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.about_button.setToolTip('Névjegy')
        self.about_button.setAccessibleName('Névjegy')
        self.about_button.clicked.connect(self.show_about)
        controls_layout.addWidget(self.about_button)
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
        self.access_notice = QLabel()
        self.access_notice.setWordWrap(True)
        top.layout().insertWidget(1, self.access_notice)
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
        self.day_table.itemDoubleClicked.connect(lambda *_: self.extract())
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
            action.setEnabled(not (self.busy or self.extracting))
        self.actions[0].setEnabled(not (self.busy or self.extracting) and valid)
        self.actions[1].setEnabled(not (self.busy or self.extracting) and valid and self.capabilities.delete)
        self.actions[2].setEnabled(not (self.busy or self.extracting) and self.capabilities.delete and not self.access_error)
        self.update_origin_button()

    def submit(self, function, success, *, kind='main', refresh_on_error=False, failure=None, progress=None):
        if kind == 'main' and self.busy:
            return
        if kind == 'main':
            self.busy = True
            self.update_actions()
        job = Job(function, with_progress=progress is not None)
        if progress is not None:
            job.signals.progress.connect(progress)
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
        if source_error:
            origins, pending, complete = {name: 'Ismeretlen' for name in files}, (), False
        else:
            origins, pending, complete = self.zip.origin_state(source, files, entries)
        return Snapshot(DailyArchiveModel(days, daily, entries), WorkspaceModel(files, sizes, origins), pending, complete, access_error)

    def refresh(self):
        if not self.busy and not self.extracting:
            self.statusBar().showMessage('Mappák és csomagok ellenőrzése…')
            self.submit(self.snapshot, self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        selected = self.current_day()
        self.source_generation += 1
        self.archive_model, self.workspace_model = snapshot.archive, snapshot.workspace
        self.days, self.files, self.sizes = snapshot.archive.days, snapshot.workspace.files, snapshot.workspace.sizes
        self.access_error = snapshot.access_error
        self.entries, self.origin_pending = snapshot.archive.entries, snapshot.pending
        self.origins_complete = snapshot.origins_complete
        if not self.origin_pending:
            self.origin_requested = False
        notice = self.access_error
        self.access_notice.setText(notice)
        self.access_notice.setVisible(bool(notice))
        self.day_table.blockSignals(True)
        self.day_table.setUpdatesEnabled(False)
        header = self.day_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.day_table.setRowCount(len(self.days))
        row = 0
        for index, day in enumerate(self.days):
            state = snapshot.archive.states[day.date]
            display = state
            color, bold = row_appearance(state)
            self.fill(self.day_table, index,
                      [day.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in day.archives), str(len(day.documents)), display],
                      appearance=(color, bold), tooltip=day.error or display)
            self.day_table.item(index, 0).setIcon(icon('warning' if day.error or state == 'Fájlütközés' else 'zip'))
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
            self.docs_table.item(row, 0).setIcon(icon('pdf'))
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
        if not self.origin_requested or self.busy or self.extracting or self.origin_busy or not self.files or not self.origin_pending:
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
            table.item(row, 0).setIcon(icon('pdf'))
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

    def extraction_progress(self, text, done=0, total=0):
        self.extraction_label.setText(f'{text}: {done} / {total}' if total else text)
        self.extraction_bar.setRange(0, total)
        self.extraction_bar.setValue(done)
        self.extraction_label.show()
        self.extraction_bar.show()

    def finish_extraction(self):
        self.extracting = False
        self.extraction_label.hide()
        self.extraction_bar.hide()
        self.update_actions()

    def extract(self):
        day = self.current_day()
        if self.busy or self.extracting or not day or day.error or self.access_error:
            return
        self.extracting = True
        self.update_actions()
        self.extraction_progress('Kicsomagolás folyamatban…')
        service = self.service()

        def failed(text):
            self.finish_extraction()
            self.error(text)

        def prepared(plan):
            # A következő háttérművelet csak az előkészítő job lezárása után indul.
            QTimer.singleShot(0, lambda: choose(plan))

        def choose(plan):
            if plan.present == plan.total:
                self.finish_extraction()
                QMessageBox.information(self, 'Kicsomagolás',
                    'A kiválasztott nap dokumentumai már megtalálhatók a munkamappában.')
                return
            mode = 'skip'
            if plan.present:
                box = QMessageBox(self)
                box.setWindowTitle('Napi csomag kicsomagolása')
                box.setText(f'{plan.total} PDF-ből {plan.present} már megtalálható, '
                            f'{plan.total - plan.present} hiányzik a munkamappából.')
                skip = box.addButton('Meglévők kihagyása, hiányzók kicsomagolása', QMessageBox.AcceptRole)
                overwrite = box.addButton('Meglévők felülírása', QMessageBox.DestructiveRole) if self.capabilities.overwrite else None
                cancel = box.addButton('Mégse', QMessageBox.RejectRole)
                box.setDefaultButton(skip)
                box.setEscapeButton(cancel)
                box.exec_()
                clicked = box.clickedButton()
                if clicked is None or clicked not in (skip, overwrite):
                    self.finish_extraction()
                    return
                mode = 'overwrite' if clicked is overwrite else 'skip'
            self.extraction_progress('Kicsomagolás folyamatban…')
            def perform(notify):
                message = service.extract(day, mode, expected_existing=plan.existing, progress=notify)
                return message, self.snapshot()
            def done(result):
                message, snapshot = result
                self.apply_snapshot(snapshot)
                self.finish_extraction()
                self.statusBar().showMessage(message, 10000)
            self.submit(perform, done, failure=failed, refresh_on_error=True, progress=self.extraction_progress)
        self.submit(lambda: service.extraction_plan(day), prepared, failure=failed)

    def delete(self, all_files):
        day = None if all_files else self.current_day()
        if self.busy or self.extracting or self.access_error or not self.capabilities.delete or (not all_files and not day):
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
        if self.jobs or self.extracting:
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
