"""Only selection text and a narrow status message need custom drawing."""
from PySide2.QtCore import Qt, QPoint
from PySide2.QtGui import QBrush, QPalette, QPolygon, QColor
from PySide2.QtWidgets import QStyledItemDelegate, QStatusBar, QStyle, QStyleOption, QStylePainter
from . import manager
from ...surface_styles import LUNA


def selected_text_colour(colour, surface):
    if surface == LUNA:
        # All four have at least 4.5:1 contrast on the royal-blue selection.
        return QColor({'#167235':'#c0ffd0', '#885000':'#fff3c4',
                       '#ad2525':'#ffeaea', '#000000':'#ffffff'}.get(colour.name(), '#ffffff'))
    return colour


class StatusItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        brush = index.data(Qt.ForegroundRole)
        if manager().active and isinstance(brush, QBrush):
            option.palette.setColor(QPalette.HighlightedText,
                                    selected_text_colour(brush.color(), manager().name))


class ThemeStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('edpd-status')
        self.summary = self.summary_source = ''
        self.messageChanged.connect(self.setToolTip)

    def set_summary(self, full, summary):
        self.summary_source, self.summary = full, summary
        self.showMessage(full)

    def paintEvent(self, event):
        if not manager().active or not self.currentMessage():
            return super().paintEvent(event)
        painter = QStylePainter(self)
        option = QStyleOption()
        option.initFrom(self)
        painter.drawPrimitive(QStyle.PE_PanelStatusBar, option)
        grip = self.style().pixelMetric(QStyle.PM_SizeGripSize) + 8 if self.isSizeGripEnabled() else 0
        rect = self.contentsRect().adjusted(6, 0, -grip-6, 0)
        text = self.currentMessage()
        metrics = self.fontMetrics()
        if text == self.summary_source and metrics.horizontalAdvance(text) > rect.width():
            text = self.summary
        text = metrics.elidedText(text, Qt.ElideMiddle, max(0, rect.width()))
        self.style().drawItemText(painter, rect, Qt.AlignLeft | Qt.AlignVCenter,
                                  self.palette(), True, text, QPalette.WindowText)


from PySide2.QtWidgets import QComboBox, QStyleOptionComboBox


class SurfaceComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if not manager().active:
            return
        # A styled drop-down panel suppresses the native arrow. Draw a small
        # high-contrast indicator without changing the standard model or popup.
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        area = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)
        painter = QStylePainter(self)
        group = QPalette.Active if self.isEnabled() else QPalette.Disabled
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(group, QPalette.Text))
        x, y = area.center().x(), area.center().y()
        painter.drawPolygon(QPolygon([QPoint(x-4,y-2), QPoint(x+4,y-2), QPoint(x,y+3)]))
