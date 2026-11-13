from PySide2.QtCore import QEvent, QTimer
from PySide2.QtWidgets import QTableWidget, QHeaderView


class ProportionalTable(QTableWidget):
    """Resizable columns; preserve the user's proportions across panel resizing."""
    def __init__(self, headers, ratios):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.ratios = tuple(ratios)
        self._sizing = False
        self.minimum_widths = (40,) * len(headers)
        self.width_timer = QTimer(self)
        self.width_timer.setSingleShot(True)
        self.width_timer.timeout.connect(self.apply_widths)
        header = self.horizontalHeader()
        header.setMinimumSectionSize(40)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.sectionResized.connect(self.remember_widths)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Resize:
            self.width_timer.start(0)
        return super().eventFilter(watched, event)

    def apply_widths(self):
        if not self.ratios:
            return
        available = self.viewport().width()
        self._sizing = True
        try:
            minimums = self.minimum_widths
            widths = list(minimums)
            free = set(range(len(self.ratios)))
            remaining = max(available, sum(minimums))
            while free:
                weight = sum(self.ratios[i] for i in free)
                fixed = [i for i in free if remaining * self.ratios[i] / weight < minimums[i]]
                if not fixed:
                    for i in free:
                        widths[i] = round(remaining * self.ratios[i] / weight)
                    widths[max(free, key=lambda i: self.ratios[i])] += remaining - sum(widths[i] for i in free)
                    break
                for i in fixed:
                    widths[i] = minimums[i]
                    remaining -= minimums[i]
                    free.remove(i)
            for i, width in enumerate(widths):
                self.setColumnWidth(i, width)
        finally:
            self._sizing = False

    def remember_widths(self, *args):
        if not self._sizing and self.isVisible():
            widths = [self.columnWidth(i) for i in range(self.columnCount())]
            self.ratios = tuple(w / sum(widths) for w in widths)
