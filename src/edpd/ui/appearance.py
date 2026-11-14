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


def ui_style_choices():
    """Only installed native styles, followed by the two complete Longhorn styles."""
    return [('Vista' if key.lower() == 'windowsvista' else key, key)
            for key in sorted(QStyleFactory.keys(), key=lambda key:
                              {'fusion':0, 'windows':1, 'windowsvista':2}.get(key.lower(),3))] + [(name, name) for name in
                                               ('Longhorn Blue', 'Longhorn Slate')]


def resolve_ui_style(name):
    if name in ('Longhorn Blue', 'Longhorn Slate'):
        return name, 'Fusion', name
    key = next((key for label, key in ui_style_choices()[:-2]
                if isinstance(name, str) and name.lower() in (label.lower(), key.lower())), 'Fusion')
    return key, key, 'Alapértelmezett'


def apply_settings_style(settings):
    settings.ui_style, settings.qt_style, settings.surface_theme = resolve_ui_style(settings.ui_style)
    apply_style(settings.qt_style, settings.surface_theme)
