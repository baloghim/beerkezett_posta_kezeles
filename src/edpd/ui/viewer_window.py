"""Archive-only browser: no workspace, extraction, state or recovery services."""
from datetime import date
from dataclasses import replace
from pathlib import Path
from PySide2.QtCore import Qt, QTimer, QSize, QByteArray, QThreadPool
from PySide2.QtWidgets import (QMainWindow, QToolBar, QSplitter, QLabel,
                              QTableWidgetItem, QDialog, QMessageBox)
from .. import __version__
from ..config import viewer_cache_directory
from ..paths import directory
from ..zip_service import ZipService, read_document
from .browser_widgets import BrowserWidgets
from .jobs import Job
from .pdf_viewer import PDFViewer
from ..pdf_export import check_pdf_save_directory
from .icons import icon, manager, set_theme
from .appearance import apply_settings_style
from .settings_dialog import SettingsDialog
from .about_dialog import AboutDialog
from .themes.widgets import ThemeStatusBar


def check_source(settings):
    import os
    source = directory(settings.source, 'A forrásarchívum')
    with os.scandir(source) as entries:
        next(entries, None)
    return settings


def document_key(doc):
    return str(doc.archive), doc.member


class ViewerWindow(QMainWindow, BrowserWidgets):
    display_name = 'EDPD Betekintő'

    def __init__(self, settings, today_provider=date.today, startup_trace=None, auto_refresh=True):
        super().__init__()
        self.setObjectName('edpd-window')
        self.setStatusBar(ThemeStatusBar(self))
        self.settings, self.today, self.trace = settings, today_provider, startup_trace
        apply_settings_style(settings)
        settings.icon_theme = set_theme(settings.icon_theme)
        self.zip = ZipService(viewer_cache_directory(), startup_trace, archive_browser=True)
        self.jobs, self.days, self.documents, self.entries = set(), [], [], ()
        self.busy = self.preview_busy = False
        self.refresh_pending = False
        self.preview_pending = None
        self.source_generation = self.preview_generation = 0
        self.selected_signature = None
        self.setWindowTitle(f'{self.display_name} {__version__}')
        self.setWindowIcon(icon('app'))
        self.resize(1600, 900)
        self.main_toolbar = QToolBar('Műveletek')
        self.main_toolbar.setObjectName('main-toolbar')
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setIconSize(QSize(40, 40))
        self.main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        font = self.main_toolbar.font()
        points = font.pointSizeF()
        if points <= 0:
            points = font.pixelSize() * 72 / max(1, self.main_toolbar.logicalDpiY())
        font.setPointSizeF(points + 2)
        self.main_toolbar.setFont(font)
        self.addToolBar(self.main_toolbar)
        self.actions = [self.main_toolbar.addAction(icon(role), text, callback) for role, text, callback in
                        [('refresh', 'Frissítés', self.refresh), ('settings', 'Beállítások', self.configure)]]
        self.menuBar().addMenu('Súgó').addAction('Névjegy', self.show_about)
        self.split, self.left = QSplitter(Qt.Horizontal), QSplitter(Qt.Vertical)
        self.day_table = self.table(['Dátum', 'Csomag azonosítója / ZIP neve', 'PDF-ek'], (.23, .62, .15))
        self.docs_table = self.table(['Fájlnév', 'Méret', 'Forrás ZIP'], (.45, .15, .40))
        top = self.panel('EDPD mappa tartalma', self.day_table)
        self.access_notice = QLabel()
        self.access_notice.setWordWrap(True)
        top.layout().insertWidget(1, self.access_notice)
        self.left.addWidget(top)
        self.left.addWidget(self.panel('A kiválasztott napi csomag PDF-dokumentumai', self.docs_table))
        self.viewer = PDFViewer()
        self.viewer.set_paths(settings.source, None)
        self.viewer.set_pdf_save_dir(settings.default_pdf_save_dir)
        self.split.addWidget(self.left)
        self.split.addWidget(self.viewer)
        self.split.setSizes([650, 950])
        self.setCentralWidget(self.split)
        self.day_table.itemSelectionChanged.connect(self.select_day)
        self.docs_table.itemSelectionChanged.connect(self.select_document)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.update_timer()
        for value, restore in [(settings.geometry, self.restoreGeometry), (settings.panels, self.split.restoreState),
                               (settings.left_panels, self.left.restoreState)]:
            if value:
                restore(QByteArray.fromBase64(value.encode()))
        manager().subscribe(self)
        if auto_refresh:
            QTimer.singleShot(0, self.refresh)

    def show_about(self):
        AboutDialog(self).exec_()

    def error(self, text):
        self.access_notice.setText('Hiba: ' + text)
        self.statusBar().showMessage('Hiba: ' + text)

    def submit(self, function, success, failure=None, finished=None):
        job = Job(function)
        self.jobs.add(job)
        def receive(value):
            try:
                success(value)
            except Exception as exc:
                self.error(str(exc))
        def complete():
            self.jobs.discard(job)
            if finished:
                finished()
        job.signals.done.connect(receive)
        job.signals.failed.connect(failure or self.error)
        job.signals.finished.connect(complete)
        QThreadPool.globalInstance().start(job)

    def current_day(self):
        row = self.day_table.currentRow()
        return self.days[row] if 0 <= row < len(self.days) else None

    def current_document(self):
        row = self.docs_table.currentRow()
        return self.documents[row] if 0 <= row < len(self.documents) else None

    def signature(self, doc):
        stamp = next((e.stamp for e in self.entries if e.path == doc.archive), None)
        return document_key(doc), doc.size, doc.crc, stamp

    def clear_preview(self):
        self.preview_generation += 1
        self.preview_pending = None
        self.selected_signature = None
        self.viewer.clear()

    def refresh(self):
        if self.busy:
            self.refresh_pending = True
            return
        self.busy = True
        self.actions[0].setEnabled(False)
        settings, generation = replace(self.settings), self.source_generation
        def load():
            check_source(settings)
            entries = self.zip.catalogue(settings.source)
            days = self.zip.scan(settings.source, settings.history_days, today=self.today(), entries=entries)
            return days, entries
        def loaded(result):
            if generation != self.source_generation:
                return
            day = self.current_day()
            selected_date = day.date if day else None
            doc = self.current_document()
            selected_key = document_key(doc) if doc else None
            self.days, self.entries = result
            self.access_notice.clear()
            self.day_table.blockSignals(True)
            self.day_table.setRowCount(len(self.days))
            for row, item in enumerate(self.days):
                values = [item.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in item.archives), str(len(item.documents))]
                for column, text in enumerate(values):
                    cell = QTableWidgetItem(text)
                    cell.setToolTip(item.error)
                    if column == 1:
                        cell.setIcon(icon('warning' if item.error else 'zip'))
                    self.day_table.setItem(row, column, cell)
            row = next((i for i, d in enumerate(self.days) if d.date == selected_date), 0 if self.days else -1)
            self.day_table.setCurrentCell(row, 0)
            self.day_table.blockSignals(False)
            self.populate_documents(selected_key if self.current_day() and self.current_day().date == selected_date else None)
            if self.trace:
                self.trace.mark('first_background_load_finished')
                self.trace.publish('loaded')
        def failed(text):
            if generation == self.source_generation:
                self.error('A forrásarchívum nem olvasható. ' + text)
                self.clear_preview()
        def finished():
            self.busy = False
            self.actions[0].setEnabled(True)
            if self.refresh_pending:
                self.refresh_pending = False
                QTimer.singleShot(0, self.refresh)
        self.submit(load, loaded, failed, finished)

    def select_day(self):
        self.populate_documents()

    def populate_documents(self, selected_key=None):
        day = self.current_day()
        self.documents = sorted(day.documents if day else (),
                                key=lambda d: (d.name.casefold(), d.archive.name.casefold(), d.member))
        self.docs_table.blockSignals(True)
        self.docs_table.clearSelection()
        self.docs_table.setCurrentCell(-1, -1)
        self.docs_table.setRowCount(len(self.documents))
        selected = None
        for row, doc in enumerate(self.documents):
            for column, text in enumerate((doc.name, f'{doc.size / 1024:.1f} KiB', doc.archive.name)):
                cell = QTableWidgetItem(text)
                cell.setData(Qt.UserRole, document_key(doc))
                cell.setToolTip(doc.member)
                if column == 0:
                    cell.setIcon(icon('pdf'))
                self.docs_table.setItem(row, column, cell)
            if document_key(doc) == selected_key:
                selected = row
        if selected is not None:
            self.docs_table.setCurrentCell(selected, 0)
        self.docs_table.blockSignals(False)
        if selected is None:
            self.clear_preview()
        elif self.signature(self.documents[selected]) != self.selected_signature:
            self.select_document()
        if day and day.error:
            self.error(day.error)

    def select_document(self):
        doc = self.current_document()
        self.clear_preview()
        if doc is None:
            return
        day = self.current_day()
        if day and day.error:
            self.error(day.error)
            return
        self.selected_signature = self.signature(doc)
        request = (doc, self.preview_generation, self.selected_signature)
        if self.preview_busy:
            self.preview_pending = request
        else:
            self.launch_preview(request)

    def launch_preview(self, request):
        doc, generation, signature = request
        if generation != self.preview_generation:
            return
        self.preview_busy = True
        def load():
            before = doc.archive.stat()
            if (before.st_mtime_ns, before.st_size) != signature[-1]:
                raise ValueError('A ZIP megváltozott. Frissítse a listát!')
            data = read_document(doc)
            after = doc.archive.stat()
            if (after.st_mtime_ns, after.st_size) != signature[-1]:
                raise ValueError('A ZIP megváltozott olvasás közben. Frissítse a listát!')
            return data
        def loaded(data):
            if generation == self.preview_generation:
                self.viewer.open_data(data, doc.name)
        def failed(text):
            if generation == self.preview_generation:
                self.error(text)
                self.selected_signature = None
        def finished():
            self.preview_busy = False
            pending, self.preview_pending = self.preview_pending, None
            if pending:
                self.launch_preview(pending)
        self.submit(load, loaded, failed, finished)

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        candidate = dialog.result_settings()
        self.actions[1].setEnabled(False)
        source_changed = candidate.source != self.settings.source
        def save():
            if source_changed:
                check_source(candidate)
            if source_changed or candidate.default_pdf_save_dir != self.settings.default_pdf_save_dir:
                check_pdf_save_directory(candidate)
            candidate.save()
            return candidate
        def saved(value):
            source_changed = value.source != self.settings.source
            self.settings = value
            self.viewer.set_pdf_save_dir(value.default_pdf_save_dir)
            apply_settings_style(value)
            value.icon_theme = set_theme(value.icon_theme)
            self.update_timer()
            if source_changed:
                self.source_generation += 1
                self.clear_preview()
                self.days, self.documents = [], []
                self.day_table.setRowCount(0)
                self.docs_table.setRowCount(0)
                self.viewer.set_paths(value.source, None)
            self.refresh()
        self.submit(save, saved, finished=lambda: self.actions[1].setEnabled(True))

    def refresh_icons(self):
        for action, role in zip(self.actions, ('refresh', 'settings')):
            action.setIcon(icon(role))
        for row, day in enumerate(self.days):
            self.day_table.item(row, 1).setIcon(icon('warning' if day.error else 'zip'))
        for row in range(len(self.documents)):
            self.docs_table.item(row, 0).setIcon(icon('pdf'))

    def closeEvent(self, event):
        if self.jobs or self.viewer.save_job is not None:
            QMessageBox.information(self, 'Folyamatban lévő művelet', 'Kérjük, várja meg a háttérművelet befejezését.')
            event.ignore()
            return
        self.timer.stop()
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
        self.viewer.clear()
        event.accept()
