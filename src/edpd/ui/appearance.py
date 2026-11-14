from PySide2.QtWidgets import QApplication, QStyleFactory
from .themes import manager


def apply_style(name, surface_theme=None):
    """Factory Qt style + independently reversible optional surface decoration."""
    surface = manager()
    previous = surface.prepare_style_change()
    keys = QStyleFactory.keys()
    selected = next((key for key in keys if key.lower() == name.lower()), None)
    selected = selected or next((key for key in keys if key.lower() == 'fusion'), None)
    if selected:
        QApplication.instance().setStyle(QStyleFactory.create(selected))
    surface.qt_style_name = QApplication.instance().style().objectName()
    surface.finish_style_change(previous if surface_theme is None else surface_theme)
    return surface.qt_style_name


def current_style_name():
    return QApplication.instance().style().objectName() or manager().qt_style_name
