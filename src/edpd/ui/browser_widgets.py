from PySide2.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QAbstractItemView, QHeaderView
from .proportional_table import ProportionalTable


class BrowserWidgets:
    def table(self, headers, ratios=None):
        table = ProportionalTable(headers, ratios) if ratios else QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        if ratios is None:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setDefaultSectionSize(max(table.verticalHeader().defaultSectionSize() + 4, table.fontMetrics().height() + 10))
        table.setAlternatingRowColors(True)
        return table

    def panel(self, title, table):
        panel = QWidget()
        panel.setObjectName('edpd-panel')
        layout = QVBoxLayout(panel)
        label = QLabel(title)
        label.setObjectName('panel-title')
        font = label.font()
        font.setBold(True)
        font.setPointSizeF(max(8, font.pointSizeF()) + 1)
        label.setFont(font)
        panel.title_label = label
        layout.addWidget(label)
        layout.addWidget(table)
        return panel

    def update_timer(self):
        self.timer.start(self.settings.refresh_minutes * 60_000)

