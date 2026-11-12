import os
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QRunnable, QThreadPool, QByteArray
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel, QTableWidget,
                              QTableWidgetItem, QAbstractItemView, QMessageBox, QToolBar, QHeaderView, QStyle)
from ..file_service import FileService, validate_paths
from ..state_service import inventory, day_status, document_status
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


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.zip = ZipService()
        self.days, self.files = [], {}
        self.jobs = set()
        self.busy = False
        self.preview_generation = 0
        self.preview_busy = False
        self.preview_pending = False
        self.setWindowTitle('EDPD – Postai dokumentumkezelő')
        self.resize(1600, 900)
        toolbar = QToolBar('Műveletek')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.actions = []
        for title, icon, callback in [
            ('Kicsomagolás', QStyle.StandardPixmap.SP_ArrowDown, self.extract),
            ('Napi adag törlése', QStyle.StandardPixmap.SP_TrashIcon, lambda: self.delete(False)),
            ('Munkamappa ürítése', QStyle.StandardPixmap.SP_DialogDiscardButton, lambda: self.delete(True)),
            ('Frissítés', QStyle.StandardPixmap.SP_BrowserReload, self.refresh),
            ('Beállítások', QStyle.StandardPixmap.SP_FileDialogContentsView, self.configure)]:
            self.actions.append(toolbar.addAction(self.style().standardIcon(icon), title, callback))
        toolbar.widgetForAction(self.actions[1]).setStyleSheet('color: #ad2525')
        toolbar.widgetForAction(self.actions[2]).setStyleSheet('color: #ad2525')
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.left = QSplitter(Qt.Orientation.Vertical)
        self.day_table = self.table(['Dátum', 'Csomag azonosítója / ZIP neve', 'PDF-ek', 'Állapot'])
        self.docs_table = self.table(['Fájlnév', 'Méret', 'Állapot'])
        self.left.addWidget(self.panel('Napi csomagok (ZIP)', self.day_table))
        self.left.addWidget(self.panel('A kiválasztott nap dokumentumai', self.docs_table))
        self.viewer = PDFViewer()
        self.split.addWidget(self.left)
        self.split.addWidget(self.viewer)
        self.split.setSizes([560, 1040])
        self.setCentralWidget(self.split)
        self.day_table.itemSelectionChanged.connect(self.select_day)
        self.docs_table.itemSelectionChanged.connect(self.select_document)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.update_timer()
        for value, restore in [(settings.geometry, self.restoreGeometry), (settings.panels, self.split.restoreState), (settings.left_panels, self.left.restoreState)]:
            if value:
                restore(QByteArray.fromBase64(value.encode()))
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
        label.setStyleSheet('font-size: 16px; font-weight: 600; color: #19476b; padding: 8px')
        layout.addWidget(label)
        layout.addWidget(table)
        return panel

    def update_timer(self):
        self.timer.start(self.settings.refresh_minutes * 60_000)

    def submit(self, function, success, exclusive=True, refresh_on_error=False):
        if exclusive and self.busy:
            return
        if exclusive:
            self.busy = True
            for action in self.actions:
                action.setEnabled(False)
        job = Job(function)
        job.needs_refresh = False
        self.jobs.add(job)
        def receive(value):
            try:
                success(value)
            except Exception as exc:
                self.error(str(exc))
        job.signals.done.connect(receive)
        def failed(text):
            job.needs_refresh = refresh_on_error
            self.error(text)
        job.signals.failed.connect(failed)
        job.signals.finished.connect(lambda: self.finish_job(job, exclusive))
        QThreadPool.globalInstance().start(job)

    def finish_job(self, job, exclusive):
        self.jobs.discard(job)
        if exclusive:
            self.busy = False
            for action in self.actions:
                action.setEnabled(True)
            if job.needs_refresh:
                QTimer.singleShot(0, self.refresh)
        else:
            self.preview_busy = False
            if self.preview_pending:
                self.preview_pending = False
                QTimer.singleShot(0, self.select_document)

    def error(self, text):
        self.statusBar().showMessage('Hiba: ' + text)
        QMessageBox.warning(self, 'EDPD – Hiba', text)

    def current_day(self):
        row = self.day_table.currentRow()
        return self.days[row] if 0 <= row < len(self.days) else None

    def snapshot(self):
        source, target = validate_paths(self.settings.source, self.settings.target)
        days, files = self.zip.scan(source), inventory(target)
        sizes = {key: path.stat().st_size for key, path in files.items()}
        states = {(d.archive, d.member): document_status(d, files, sizes) for day in days for d in day.documents}
        daily = {day.date: day_status(day, files, sizes) for day in days}
        return days, files, states, daily

    def refresh(self):
        if not self.busy:
            self.statusBar().showMessage('Mappák és csomagok ellenőrzése…')
            self.submit(self.snapshot, self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        selected = self.current_day()
        self.days, self.files, self.states, daily = snapshot
        self.day_table.blockSignals(True)
        self.day_table.setRowCount(len(self.days))
        row = 0
        for index, day in enumerate(self.days):
            self.fill(self.day_table, index, [day.date.strftime('%Y.%m.%d.'), ', '.join(p.name for p in day.archives), str(len(day.documents)), daily[day.date]])
            if day.error:
                for col in range(4):
                    self.day_table.item(index, col).setToolTip(day.error)
            if selected and day.date == selected.date:
                row = index
        if self.days:
            self.day_table.selectRow(row)
        self.day_table.blockSignals(False)
        self.select_day()
        self.statusBar().showMessage(f'Forrás: {self.settings.source}  |  Cél: {self.settings.target}  |  {len(self.files)} PDF  |  Elérhető  |  Frissítve: {datetime.now():%H:%M:%S}')

    def fill(self, table, row, values):
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            table.setItem(row, col, item)

    def select_day(self):
        day = self.current_day()
        self.preview_generation += 1
        self.docs_table.blockSignals(True)
        self.docs_table.clearContents()
        self.docs_table.setRowCount(len(day.documents) if day else 0)
        if day:
            for row, doc in enumerate(day.documents):
                self.fill(self.docs_table, row, [doc.name, f'{doc.size / 1024:,.1f} KiB', self.states[(doc.archive, doc.member)]])
        self.docs_table.clearSelection()
        self.docs_table.setCurrentCell(-1, -1)
        self.docs_table.blockSignals(False)

    def select_document(self):
        day = self.current_day()
        row = self.docs_table.currentRow()
        if not day or row < 0:
            return
        doc = day.documents[row]
        self.preview_generation += 1
        generation = self.preview_generation
        if self.preview_busy:
            self.preview_pending = True
            return
        self.preview_busy = True
        target = self.settings.target
        def load():
            files = inventory(__import__('pathlib').Path(target))
            path = files.get(doc.name.casefold())
            if path:
                with open(path, 'rb') as stream:
                    data = stream.read(MAX_PDF + 1)
                if len(data) > MAX_PDF:
                    raise ValueError('A PDF meghaladja a 256 MiB biztonsági korlátot.')
                return data
            return read_document(doc)
        self.submit(load, lambda data: self.viewer.open_data(data) if generation == self.preview_generation else None, exclusive=False)

    def service(self):
        return FileService(self.settings.source, self.settings.target)

    def extract(self):
        day = self.current_day()
        if not day:
            return
        # Minden esetben kérdés: az előzetes listázás óta másik gép is létrehozhatott PDF-et.
        box = QMessageBox(self)
        box.setWindowTitle('Napi csomag kicsomagolása')
        existing = sum(d.name.casefold() in self.files for d in day.documents)
        box.setText(f'A napi csomag {len(day.documents)} PDF-et tartalmaz; a legutóbbi frissítéskor {existing} már a munkamappában volt. Válasszon műveletet!')
        skip = box.addButton('Meglévők kihagyása', QMessageBox.ButtonRole.AcceptRole)
        overwrite = box.addButton('Meglévők felülírása', QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton('Mégse', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() not in (skip, overwrite):
            return
        mode = 'overwrite' if box.clickedButton() == overwrite else 'skip'
        service = self.service()
        self.submit(lambda: (service.extract(day, mode), self.snapshot()), self.operation_done, refresh_on_error=True)

    def delete(self, all_files):
        day = None if all_files else self.current_day()
        if not all_files and not day:
            return
        service = self.service()
        # A hálózati előellenőrzés is háttérben fut.
        def prepare():
            _, target = validate_paths(service.source, service.target)
            files = inventory(target)
            names = set(files) if all_files else set(files) & {d.name.casefold() for d in day.documents}
            if day:
                days = self.zip.scan(service.source)
                shared = names & {d.name.casefold() for other in days if other.date != day.date for d in other.documents}
                if shared:
                    raise ValueError('Napi törlés nem végezhető: több napi csomaghoz tartozó fájlnév: ' + ', '.join(sorted(shared)))
            return names
        def confirm(names):
            title = 'Teljes munkamappa ürítése' if all_files else f'{day.date:%Y.%m.%d.} napi adag törlése'
            if QMessageBox.question(self, title, f'Biztosan törli a munkamappából a(z) {len(names)} PDF-et?\nA törlés nem vonható vissza.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                # A finished jel után indítható az új kizárólagos feladat.
                QTimer.singleShot(0, lambda: self.submit(lambda: (service.delete(day, confirmed=True, expected_names=names), self.snapshot()), self.operation_done, refresh_on_error=True))
        self.submit(prepare, confirm)

    def operation_done(self, result):
        message, snapshot = result
        self.apply_snapshot(snapshot)
        QMessageBox.information(self, 'Művelet eredménye', message)

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            candidate = dialog.result_settings()
            def save():
                check_settings(candidate)
                candidate.save()
                return candidate
            def saved(value):
                self.settings = value
                self.update_timer()
                QTimer.singleShot(0, self.refresh)
            self.submit(save, saved)

    def closeEvent(self, event):
        if self.jobs:
            QMessageBox.information(self, 'Folyamatban lévő művelet', 'Kérjük, várja meg a háttérművelet befejezését.')
            event.ignore()
            return
        self.settings.geometry = bytes(self.saveGeometry().toBase64()).decode()
        self.settings.panels = bytes(self.split.saveState().toBase64()).decode()
        self.settings.left_panels = bytes(self.left.saveState().toBase64()).decode()
        try:
            self.settings.save()
        except OSError as exc:
            self.error(str(exc))
            event.ignore()
            return
        if self.viewer.pdf:
            self.viewer.pdf.close()
        event.accept()
