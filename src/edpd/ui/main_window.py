from datetime import date, datetime
import threading
import time
from pathlib import Path
from dataclasses import dataclass
from PySide2.QtCore import Qt, QTimer, QObject, Signal, QSize, QRunnable, QThreadPool, QByteArray
from PySide2.QtGui import QColor, QBrush, QPalette, QFontMetrics, QIcon
from .. import __version__, DISPLAY_NAME
from PySide2.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QMessageBox, QToolBar, QHeaderView,
                              QDialog, QPushButton, QAction, QSizePolicy, QToolButton, QHBoxLayout,
                              QApplication, QStyle, QStyleOptionViewItem)
from ..config import cache_directory
from ..file_service import FileService, validate_paths
from ..models import Capabilities
from ..paths import directory
from ..state_service import inventory, day_status
from ..zip_service import ZipService, read_document, MAX_PDF
from .pdf_viewer import PDFViewer
from .icons import icon, manager, set_theme, ThemedMenu as QMenu
from .settings_dialog import SettingsDialog, check_settings
from .browser_widgets import BrowserWidgets
from .jobs import Job
from .extraction_dialog import ExtractionDialog
from .themes import manager as surface_manager, set_theme as set_surface_theme
from .themes.widgets import StatusItemDelegate, ThemeStatusBar
from ..processed_store import ProcessedStore, packet_id
from ..shared_processed_store import SharedProcessedStore, SharedState, shared_packet_id


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
    processed: frozenset = frozenset()
    mark_error: str = ''
    source_identity: str = ''
    shared_state: SharedState | None = None


def row_appearance(state):
    if state == 'Kicsomagolva':
        return '#000000', True
    if state == 'Részben kicsomagolva':
        return '#885000', True
    if state in ('Hibás csomag', 'Fájlütközés'):
        return '#ad2525', True
    return None, False


class ProcessedIconDelegate(StatusItemDelegate):
    def paint(self, painter, option, index):
        cell = QStyleOptionViewItem(option)
        self.initStyleOption(cell, index)
        status_icon = cell.icon
        cell.features = cell.features & ~QStyleOptionViewItem.HasDecoration
        style = cell.widget.style() if cell.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, cell, painter, cell.widget)
        size = min(cell.rect.width(), cell.rect.height(), 22)
        bounds = QStyle.alignedRect(cell.direction, Qt.AlignCenter, QSize(size, size), cell.rect)
        status_icon.paint(painter, bounds)


class MainWindow(QMainWindow, BrowserWidgets):
    def __init__(self, settings, capabilities=Capabilities(), today_provider=date.today, startup_trace=None, auto_refresh=True):
        super().__init__()
        self.setObjectName('edpd-window')
        self.setStatusBar(ThemeStatusBar(self))
        from .appearance import apply_settings_style
        apply_settings_style(settings)
        self.trace = startup_trace
        self.first_refresh_started = None
        settings.icon_theme = set_theme(settings.icon_theme)
        self.settings, self.capabilities, self.today = settings, capabilities, today_provider
        self.zip = ZipService(cache_dir=cache_directory(), startup_trace=startup_trace)
        self.days, self.files, self.sizes = [], {}, {}
        self.work_keys, self.entries, self.origin_pending = [], (), ()
        self.origins_complete, self.access_error = True, ''
        self.archive_model = DailyArchiveModel([], {}, ())
        self.workspace_model = WorkspaceModel({}, {}, {})
        self.origin_requested = False
        self.processed, self.mark_error = frozenset(), ''
        self.source_identity = settings.source
        self.shared_state = None
        self.shared_mark_rows = {}
        self.mark_polling = False
        self.mark_generation = 0
        self.jobs = set()
        self.busy = self.preview_busy = self.origin_busy = False
        self.preview_generation = self.source_generation = 0
        self.preview_pending = None
        self.extracting = False
        self.extraction_dialog = None
        self.cancel_extraction = threading.Event()
        self.setWindowTitle(f'{DISPLAY_NAME} {__version__}')
        self.setWindowIcon(icon('app'))
        self.resize(1600, 900)
        toolbar = QToolBar('Műveletek')
        toolbar.setIconSize(QSize(40, 40))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        main_font = toolbar.font()
        base_points = main_font.pointSizeF()
        if base_points <= 0:  # A pixel-sized application font still needs +2 points.
            dpi = toolbar.logicalDpiY()
            base_points = main_font.pixelSize() * 72 / (dpi if dpi > 0 else 96)
        main_font.setPointSizeF(base_points + 2)
        toolbar.setFont(main_font)
        toolbar.setObjectName('main-toolbar')
        self.main_toolbar = toolbar
        self.toolbar_controls = QWidget()
        self.toolbar_controls.setObjectName('toolbar-controls')
        self.toolbar_controls.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_layout = QHBoxLayout(self.toolbar_controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self.toolbar_controls)
        # Only operation buttons may overflow; About always keeps its own space.
        toolbar = QToolBar('Műveleti gombok')
        toolbar.setFont(main_font)
        toolbar.setObjectName('operation-toolbar')
        self.operation_toolbar = toolbar
        toolbar.layout().setSpacing(6)
        toolbar.setIconSize(QSize(40, 40))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        controls_layout.addWidget(toolbar, 1)
        self.actions = []
        self.action_roles = []
        for title, icon_name, callback in [
            ('Kicsomagolás', 'extract', self.extract),
            ('Kijelölt nap fájljainak törlése', 'delete', lambda: self.delete(False)),
            ('Munkamappa ürítése', 'clear', lambda: self.delete(True)),
            ('Frissítés', 'refresh', self.refresh),
            ('Beállítások', 'settings', self.configure)]:
            self.actions.append(toolbar.addAction(icon(icon_name), title, callback))
            self.actions[-1].setFont(main_font)
            self.action_roles.append(icon_name)
        self.about_button = QToolButton()
        self.about_button.setIcon(icon('about'))
        self.about_button.setIconSize(QSize(40, 40))
        self.about_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.about_button.setToolTip('Névjegy')
        self.about_button.setAccessibleName('Névjegy')
        self.about_button.clicked.connect(self.show_about)
        controls_layout.addWidget(self.about_button)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.left = QSplitter(Qt.Orientation.Vertical)
        self.day_table = self.table(['Dátum', 'Csomag azonosítója / ZIP neve', 'PDF-ek', 'Állapot', 'Feldolgozva'],
                                    (.17, .43, .09, .23, .08))
        self.docs_table = self.table(['Dátum', 'Fájlnév', 'Méret'], (.21, .64, .15))
        self.day_table.setItemDelegate(StatusItemDelegate(self.day_table))
        self.day_table.setItemDelegateForColumn(4, ProcessedIconDelegate(self.day_table))
        bold_font = self.day_table.font()
        bold_font.setBold(True)
        metrics = QFontMetrics(bold_font)
        date_width = metrics.horizontalAdvance('2000.00.00.') + 12
        header_metrics = self.day_table.horizontalHeader().fontMetrics()
        header_widths = tuple(header_metrics.horizontalAdvance(
            self.day_table.horizontalHeaderItem(col).text()) + 18 for col in range(5))
        self.day_table.minimum_widths = (
            max(date_width, header_widths[0]), header_widths[1], header_widths[2],
            max(metrics.horizontalAdvance('Részben kicsomagolva') + 12, header_widths[3]),
            header_widths[4],
        )
        self.docs_table.minimum_widths = (date_width, 80, 60)
        self.docs_table.horizontalHeaderItem(0).setToolTip('Az eredeti napi ZIP-csomag dátuma. Ismeretlen eredetnél Ismeretlen.')
        top = self.panel('EDPD mappa tartalma', self.day_table)
        self.access_notice = QLabel()
        self.access_notice.setWordWrap(True)
        top.layout().insertWidget(1, self.access_notice)
        self.restore_marks_button = QPushButton('Közös jelzők helyreállítása…')
        self.restore_marks_button.clicked.connect(self.restore_shared_marks)
        self.restore_marks_button.hide()
        top.layout().insertWidget(2, self.restore_marks_button)
        self.left.addWidget(top)
        self.workspace_panel = self.panel('A munkamappa dokumentumai', self.docs_table)
        self.origin_button = QPushButton('További forráskeresés')
        self.origin_button.setToolTip('Csak külön kérésre nyitjuk meg a még nem ismert régebbi ZIP-eket.')
        self.origin_button.clicked.connect(self.request_origin_search)
        self.workspace_panel.layout().insertWidget(1, self.origin_button)
        self.left.addWidget(self.workspace_panel)
        self.viewer = PDFViewer()
        self.viewer.set_paths(settings.source, settings.target)
        self.viewer.saved.connect(lambda path: self.statusBar().showMessage('PDF mentve: ' + path, 10000))
        self.split.addWidget(self.left)
        self.split.addWidget(self.viewer)
        self.split.setSizes([780, 820])
        self.setCentralWidget(self.split)
        self.day_table.itemSelectionChanged.connect(self.select_day)
        self.day_table.itemDoubleClicked.connect(lambda *_: self.extract())
        self.day_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.day_table.customContextMenuRequested.connect(self.show_day_menu)
        self.archive_preview_action = QAction('ZIP-csomag PDF-jeinek megtekintése…', self.day_table)
        self.archive_preview_action.triggered.connect(self.browse_day)
        self.day_table.addAction(self.archive_preview_action)
        self.processed_action = QAction('Feldolgozva', self.day_table)
        self.processed_action.triggered.connect(lambda: self.mark_day(self.current_day()))
        self.day_table.setToolTip('Jobb kattintás: ZIP-betekintés. A nap kiválasztása nem változtatja a munkamappa-listát.')
        self.docs_table.itemSelectionChanged.connect(self.select_document)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.mark_timer = QTimer(self)
        self.mark_timer.setInterval(15_000)
        self.mark_timer.timeout.connect(self.poll_shared_marks)
        self.update_mark_timer()
        self.origin_timer = QTimer(self)
        self.origin_timer.setSingleShot(True)
        self.origin_timer.timeout.connect(self.lookup_origins)
        self.update_timer()
        for value, restore in [(settings.geometry, self.restoreGeometry), (settings.panels, self.split.restoreState), (settings.left_panels, self.left.restoreState)]:
            if value:
                restore(QByteArray.fromBase64(value.encode()))
        self.update_actions()
        manager().subscribe(self)
        self.refresh_icons()
        if auto_refresh:
            QTimer.singleShot(0, self.refresh)

    def update_actions(self):
        day = self.current_day()
        valid = day is not None and not day.error and not self.access_error
        for action in self.actions:
            action.setEnabled(not (self.busy or self.extracting))
        self.actions[0].setEnabled(not (self.busy or self.extracting) and valid)
        self.actions[1].setEnabled(not (self.busy or self.extracting) and valid and self.capabilities.delete)
        self.actions[2].setEnabled(not (self.busy or self.extracting) and self.capabilities.delete and not self.access_error)
        self.processed_action.setVisible(self.capabilities.processed)
        self.processed_action.setEnabled(not (self.busy or self.extracting) and day is not None and not self.mark_error and self.capabilities.processed)
        if self.uses_shared_marks() and day is not None and day.error:
            self.processed_action.setEnabled(False)
        can_restore = self.shared_state is not None and self.shared_state.recovery is not None
        self.restore_marks_button.setVisible(can_restore)
        self.restore_marks_button.setEnabled(not (self.busy or self.extracting))
        marked = day is not None and self.mark_key(day) in self.processed
        self.processed_action.setText('Feldolgozás visszavonása' if marked else 'Feldolgozva')
        self.update_origin_button()

    def submit(self, function, success, *, kind='main', refresh_on_error=False, failure=None, progress=None):
        if kind == 'main' and self.busy:
            return
        if kind == 'main':
            self.busy = True
            self.mark_generation += 1
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
                load, generation, filename = self.preview_pending
                self.preview_pending = None
                QTimer.singleShot(0, lambda: self.launch_preview(load, generation, filename))
        elif kind == 'marks':
            self.mark_polling = False
        else:
            self.origin_busy = False
        if self.origin_requested and self.files and self.origin_pending and not self.origin_busy:
            self.origin_timer.start(250)

    def error(self, text):
        self.statusBar().showMessage('Hiba: ' + text)
        QMessageBox.warning(self, f'{DISPLAY_NAME} – Hiba', text)

    def current_day(self):
        row = self.day_table.currentRow()
        return self.days[row] if 0 <= row < len(self.days) else None

    def read_workspace(self, settings):
        started = time.perf_counter()
        try:
            target = directory(settings.target, 'A munkamappa')
            files = inventory(target)
            sizes = {key: path.stat().st_size for key, path in files.items()}
            return WorkspaceModel(files, sizes, {}), target, ''
        except Exception as exc:
            return WorkspaceModel({}, {}, {}), None, 'A munkamappa nem olvasható: ' + str(exc)
        finally:
            if self.trace:
                self.trace.add('workspace_check_ms', (time.perf_counter() - started) * 1000)

    def read_daily_archives(self, settings):
        before = time.perf_counter()
        try:
            source = directory(settings.source, 'A forrásarchívum')
            if self.trace:
                self.trace.add('source_directory_check_ms', (time.perf_counter() - before) * 1000)
            started = time.perf_counter()
            entries = self.zip.catalogue(source)
            if self.trace:
                self.trace.add('zip_catalogue_ms', (time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            days = self.zip.scan(source, settings.history_days, today=self.today(), entries=entries)
            if self.trace:
                self.trace.add('zip_filtered_scan_ms', (time.perf_counter() - started) * 1000)
            return DailyArchiveModel(days, {}, entries), source, ''
        except Exception as exc:
            if self.trace:
                self.trace.add('source_directory_check_ms', (time.perf_counter() - before) * 1000)
            return DailyArchiveModel([], {}, ()), None, str(exc)

    def snapshot(self):
        if self.trace and self.trace.network_delay_ms:
            time.sleep(self.trace.network_delay_ms / 1000)
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
                FileService.check_recovery(target)
            except Exception as exc:
                guard_error = str(exc)
        access_error = '\n'.join(e for e in (source_error, target_error, guard_error) if e)
        daily = {day.date: ('Munkamappa nem érhető el' if target_error else day_status(day, files, sizes)) for day in days}
        if source_error:
            origins, pending, complete = {name: 'Ismeretlen' for name in files}, (), False
        else:
            origins, pending, complete = self.zip.origin_state(source, files, entries)
        state = self.read_shared_marks(settings) if self.uses_shared_marks() else None
        processed, mark_error = frozenset(), ''
        if state is None and self.capabilities.processed:
            try:
                processed = frozenset(ProcessedStore(settings.source, settings.target).read())
            except Exception as exc:
                mark_error = 'Helyi Feldolgozva állapot nem olvasható: ' + str(exc)
        return Snapshot(DailyArchiveModel(days, daily, entries), WorkspaceModel(files, sizes, origins),
                        pending, complete, access_error, processed, mark_error,
                        str(source) if source is not None else settings.source, state)

    def refresh(self):
        if not self.busy and not self.extracting:
            if self.trace and self.first_refresh_started is None:
                self.first_refresh_started = time.perf_counter()
                self.trace.mark('first_background_load_started')
            self.statusBar().showMessage('Dokumentumok és napi csomagok betöltése…')
            self.submit(self.snapshot, self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        selected = self.current_day()
        self.source_generation += 1
        self.archive_model, self.workspace_model = snapshot.archive, snapshot.workspace
        self.days, self.files, self.sizes = snapshot.archive.days, snapshot.workspace.files, snapshot.workspace.sizes
        self.access_error = snapshot.access_error
        if snapshot.shared_state is None:
            self.processed, self.mark_error = snapshot.processed, snapshot.mark_error
        else:
            self.receive_shared_state(snapshot.shared_state, update_table=False)
        self.source_identity = snapshot.source_identity
        self.entries, self.origin_pending = snapshot.archive.entries, snapshot.pending
        self.origins_complete = snapshot.origins_complete
        if not self.origin_pending:
            self.origin_requested = False
        self.update_mark_notice()
        self.day_table.blockSignals(True)
        self.day_table.setUpdatesEnabled(False)
        self.day_table.setRowCount(len(self.days))
        row = 0
        self.shared_mark_rows = {}
        for index, day in enumerate(self.days):
            state = snapshot.archive.states[day.date]
            self.fill(self.day_table, index,
                      [day.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in day.archives), str(len(day.documents)), state, ''],
                      appearance=row_appearance(state), tooltip=day.error or state)
            self.day_table.item(index, 2).setTextAlignment(Qt.AlignCenter)
            key = self.mark_key(day)
            if self.uses_shared_marks():
                self.shared_mark_rows.setdefault(key, []).append(index)
            self.set_mark_cell(index, key)
            self.day_table.item(index, 1).setIcon(icon('warning' if day.error or state == 'Fájlütközés' else 'zip'))
            if selected and day.date == selected.date:
                row = index
        if self.days:
            self.day_table.selectRow(row)
        self.day_table.setUpdatesEnabled(True)
        self.day_table.blockSignals(False)
        self.populate_workspace(snapshot.workspace.origins)
        self.select_day()
        self.last_refresh = datetime.now()
        self.show_status()
        if self.trace:
            if self.first_refresh_started is not None:
                self.trace.add('first_automatic_refresh_ms', (time.perf_counter() - self.first_refresh_started) * 1000)
            self.trace.mark('first_background_load_finished')
            self.trace.publish('loaded', access_error=bool(self.access_error))

    def populate_workspace(self, origins):
        row = self.docs_table.currentRow()
        selected = self.work_keys[row] if 0 <= row < len(self.work_keys) else None
        def order(key):
            try:
                ordinal = datetime.strptime(origins.get(key, ''), '%Y.%m.%d.').date().toordinal()
            except ValueError:
                ordinal = 0
            return -ordinal, self.files[key].name.casefold(), self.files[key].name
        self.work_keys = sorted(self.files, key=order)
        self.docs_table.blockSignals(True)
        self.docs_table.setUpdatesEnabled(False)
        self.docs_table.clearContents()
        self.docs_table.setRowCount(len(self.work_keys))
        self.docs_table.setCurrentCell(-1, -1)
        for row, key in enumerate(self.work_keys):
            self.fill(self.docs_table, row, [origins.get(key, 'Ismeretlen'), self.files[key].name, f'{self.sizes[key] / 1024:,.1f} KiB'])
            self.docs_table.item(row, 1).setIcon(icon('pdf'))
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
        full = f'v{__version__}  |  Időszak: {period}  |  Forrás: {self.settings.source}  |  Cél: {self.settings.target}  |  {len(self.files)} PDF  |  Frissítve: {self.last_refresh:%H:%M:%S}  |  {progress}'
        summary = f'v{__version__}  |  {period}  |  {len(self.files)} PDF  |  Frissítve: {self.last_refresh:%H:%M:%S}  |  {progress}'
        self.statusBar().set_summary(full, summary)

    def update_origin_button(self):
        self.origin_button.setVisible(bool(self.origin_pending))
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
            self.populate_workspace(labels)
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
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setToolTip(value + ('\n' + tooltip if tooltip and tooltip != value else ''))
            if appearance is not None:
                color, bold = appearance
                if color:
                    item.setForeground(QBrush(QColor(color)))
                font = item.font()
                font.setBold(bold)
                item.setFont(font)
            table.setItem(row, col, item)

    def select_day(self):
        # A felső lista navigálása nem szűri a munkamappát, nem nyit új PDF-et.
        self.update_actions()

    def open_preview(self, load, filename='dokumentum.pdf'):
        self.preview_generation += 1
        generation = self.preview_generation
        if self.preview_busy:
            self.preview_pending = (load, generation, filename)
        else:
            self.launch_preview(load, generation, filename)

    def launch_preview(self, load, generation, filename='dokumentum.pdf'):
        if generation != self.preview_generation:
            return
        self.preview_busy = True
        self.submit(load, lambda data: self.viewer.open_data(data, filename) if generation == self.preview_generation else None, kind='preview')

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
        self.open_preview(load, self.files[key].name)

    def open_archive_document(self, document):
        self.open_preview(lambda: read_document(document), document.name)

    def browse_day(self, *args, day=None):
        day = day or self.current_day()
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
        def refresh_preview_icons():
            for row in range(table.rowCount()):
                table.item(row, 0).setIcon(icon('pdf'))
        dialog.refresh_icons = refresh_preview_icons
        manager().subscribe(dialog)
        dialog.exec_()

    def show_day_menu(self, pos):
        row = self.day_table.indexAt(pos).row()
        if not 0 <= row < len(self.days):
            return
        self.day_table.selectRow(row)
        day = self.days[row]
        menu = QMenu(self)
        preview = menu.addAction(icon('zip'), 'ZIP-csomag PDF-jeinek megtekintése…')
        preview.setProperty('icon_role', 'zip')
        preview.setEnabled(not day.error)
        preview.triggered.connect(lambda: self.browse_day(day=day))
        if self.capabilities.processed:
            action = menu.addAction(icon('about'), self.processed_action.text())
            action.setProperty('icon_role', 'about')
            action.setEnabled(self.processed_action.isEnabled())
            action.triggered.connect(lambda: self.mark_day(day))
        menu.exec_(self.day_table.viewport().mapToGlobal(pos))

    def uses_shared_marks(self):
        return self.capabilities.processed and self.settings.shared_workspace

    def mark_key(self, day):
        if self.uses_shared_marks():
            return shared_packet_id(day)
        return packet_id(self.source_identity, day, canonical=True)

    def update_mark_timer(self):
        if self.uses_shared_marks():
            self.mark_timer.start()
        else:
            self.mark_timer.stop()

    def update_mark_notice(self):
        notice = '\n'.join(filter(None, (self.access_error, self.mark_error)))
        self.access_notice.setText(notice)
        self.access_notice.setVisible(bool(notice))

    def set_mark_cell(self, row, key):
        marker = self.day_table.item(row, 4)
        marked = key in self.processed and (self.uses_shared_marks() or not self.mark_error)
        marker.setData(Qt.UserRole, 'processed' if marked else None)
        marker.setIcon(icon('processed') if marked else QIcon())
        local_error = '' if self.uses_shared_marks() else self.mark_error
        marker.setToolTip(local_error or ('Feldolgozva' if marked else ''))

    @staticmethod
    def read_shared_marks(settings, cached=None):
        try:
            return SharedProcessedStore(settings.source, settings.target).inspect(cached)
        except Exception as exc:
            return SharedState(error=f'A közös feldolgozottsági állapot nem olvasható: {exc}')

    def receive_shared_state(self, state, *, update_table=True):
        if state == self.shared_state and update_table:
            return
        previous = self.processed
        self.shared_state = state
        self.mark_error = state.error
        if state.packets is not None:
            self.processed = state.packets
        if update_table:
            self.update_mark_notice()
            for key in previous ^ self.processed:
                for row in self.shared_mark_rows.get(key, ()):
                    self.set_mark_cell(row, key)
            self.update_actions()

    def poll_shared_marks(self):
        if not self.uses_shared_marks() or self.busy or self.extracting or self.mark_polling:
            return
        self.mark_polling = True
        settings, cached, generation = self.settings, self.shared_state, self.mark_generation
        def received(state):
            if generation == self.mark_generation and self.uses_shared_marks():
                self.receive_shared_state(state)
        self.submit(lambda: self.read_shared_marks(settings, cached), received, kind='marks')

    def shared_write_failed(self, text):
        self.receive_shared_state(SharedState(error=f'A közös művelet nem ellenőrizhető: {text}'))
        self.error(self.mark_error)
        QTimer.singleShot(0, self.poll_shared_marks)

    def restore_shared_marks(self):
        if (not self.uses_shared_marks() or self.busy or self.extracting
                or self.shared_state is None or self.shared_state.recovery is None):
            return
        expected = self.shared_state.recovery
        settings = self.settings
        if QMessageBox.question(self, 'Közös jelzők helyreállítása',
                                'Visszaállítja a közös jelzőket a biztonsági másolatból? '
                                'Az utolsó módosítás elveszhet.',
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if self.settings is not settings or self.extracting:
            return
        store = SharedProcessedStore(settings.source, settings.target)
        self.submit(lambda: store.restore(expected), self.receive_shared_state, failure=self.shared_write_failed)

    def mark_day(self, day):
        if not day or not self.capabilities.processed or self.busy or self.extracting or self.mark_error:
            return
        key = self.mark_key(day)
        desired = key not in self.processed
        if self.uses_shared_marks():
            if day.error or self.shared_state is None:
                return
            store = SharedProcessedStore(self.settings.source, self.settings.target)
            self.submit(lambda: store.set_processed(key, desired), self.receive_shared_state,
                        failure=self.shared_write_failed)
            return

        def write():
            ProcessedStore(self.settings.source, self.settings.target, self.capabilities).set_processed(day, desired)
            return self.snapshot()
        self.submit(write, self.apply_snapshot)

    def service(self):
        return FileService(self.settings.source, self.settings.target, self.capabilities, zip_service=self.zip)

    def extraction_progress(self, text, done=0, total=0):
        if self.extraction_dialog:
            self.extraction_dialog.update_progress(text, done, total)

    def finish_extraction(self, success=True):
        self.extracting = False
        if self.extraction_dialog:
            self.extraction_dialog.complete(success)
        self.update_actions()

    def extract(self):
        day = self.current_day()
        if self.busy or self.extracting or not day or day.error or self.access_error:
            return
        self.extracting = True
        self.update_actions()
        self.cancel_extraction = threading.Event()
        if self.extraction_dialog is not None:
            self.extraction_dialog.deleteLater()
        self.extraction_dialog = ExtractionDialog(day, self)
        self.extraction_dialog.cancel_requested.connect(self.cancel_extraction.set)
        self.extraction_label, self.extraction_bar = self.extraction_dialog.label, self.extraction_dialog.bar
        self.extraction_dialog.open()
        service = self.service()

        def failed(text):
            self.finish_extraction(False)
            self.error(text)

        def prepared(plan):
            # A következő háttérművelet csak az előkészítő job lezárása után indul.
            QTimer.singleShot(0, lambda: choose(plan))

        def choose(plan):
            if self.cancel_extraction.is_set():
                self.finish_extraction(False)
                self.statusBar().showMessage('A kicsomagolás megszakítva; nem történt módosítás.', 10000)
                return
            if plan.present == plan.total:
                self.finish_extraction()
                QMessageBox.information(self, 'Kicsomagolás',
                    'A kiválasztott nap dokumentumai már megtalálhatók a munkamappában.')
                return
            mode = 'skip'
            if plan.present:
                self.extraction_dialog.hide()
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
            self.extraction_dialog.open()
            self.extraction_progress('Kicsomagolás folyamatban…')
            def perform(notify):
                message = service.extract(day, mode, expected_existing=plan.existing, progress=notify, cancel=self.cancel_extraction)
                return message, self.snapshot()
            def done(result):
                message, snapshot = result
                self.apply_snapshot(snapshot)
                self.finish_extraction(not self.cancel_extraction.is_set())
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
            previous = self.settings
            path_changed = (candidate.source, candidate.target) != (previous.source, previous.target)
            workflow_changed = any(getattr(candidate, field) != getattr(previous, field)
                                   for field in ('source', 'target', 'history_days', 'refresh_minutes'))
            mark_storage_changed = (candidate.shared_workspace != previous.shared_workspace
                                    or (candidate.shared_workspace and candidate.target != previous.target))
            def save():
                if path_changed:
                    check_settings(candidate)
                if self.capabilities.processed and candidate.shared_workspace and (mark_storage_changed or path_changed):
                    SharedProcessedStore(candidate.source, candidate.target).prepare()
                candidate.save()
                return candidate
            def saved(value):
                self.settings = value
                if mark_storage_changed:
                    self.processed = frozenset()
                    self.shared_state = None
                    self.mark_error = 'Feldolgozottsági jelzők betöltése…'
                    self.update_mark_timer()
                    self.update_mark_notice()
                    for row, day in enumerate(self.days):
                        self.set_mark_cell(row, self.mark_key(day))
                    QTimer.singleShot(0, self.refresh)
                from .appearance import apply_settings_style
                apply_settings_style(value)
                value.surface_theme = surface_manager().name
                value.icon_theme = set_theme(value.icon_theme)
                if workflow_changed:
                    self.origin_requested = False
                    self.origin_timer.stop()
                    self.viewer.set_paths(value.source, value.target)
                    self.preview_generation += 1
                    self.source_generation += 1
                    self.update_timer()
                    if not mark_storage_changed:
                        QTimer.singleShot(0, self.refresh)
            self.submit(save, saved)

    def refresh_icons(self):
        for action, role in zip(self.actions, self.action_roles):
            action.setIcon(icon(role))
        self.about_button.setIcon(icon('about'))
        self.archive_preview_action.setIcon(icon('zip'))
        self.processed_action.setIcon(icon('about'))
        self.day_table.setUpdatesEnabled(False)
        self.docs_table.setUpdatesEnabled(False)
        try:
            for row, day in enumerate(self.days):
                state = self.archive_model.states.get(day.date, '')
                self.day_table.item(row, 1).setIcon(icon('warning' if day.error or state == 'Fájlütközés' else 'zip'))
                marker = self.day_table.item(row, 4)
                if marker is not None:
                    role = marker.data(Qt.UserRole)
                    if role:
                        marker.setIcon(icon(role))
            for row in range(self.docs_table.rowCount()):
                self.docs_table.item(row, 1).setIcon(icon('pdf'))
        finally:
            self.day_table.setUpdatesEnabled(True)
            self.docs_table.setUpdatesEnabled(True)

    def closeEvent(self, event):
        if self.jobs or self.extracting or self.viewer.save_job is not None:
            QMessageBox.information(self, 'Folyamatban lévő művelet', 'Kérjük, várja meg a háttérművelet befejezését.')
            event.ignore()
            return
        self.origin_timer.stop()
        self.mark_timer.stop()
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
