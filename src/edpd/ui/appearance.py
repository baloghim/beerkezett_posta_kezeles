from PySide2.QtWidgets import QApplication, QStyleFactory
from .themes import manager
from ..surface_styles import CUSTOM_SURFACES, DEFAULT_SURFACE


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


def native_style_choices():
    return [('Vista' if key.lower() == 'windowsvista' else key, key)
            for key in sorted(QStyleFactory.keys(), key=lambda key:
                              {'fusion':0, 'windows':1, 'windowsvista':2}.get(key.lower(),3))]


def ui_style_choices():
    """Installed factory styles followed by the centrally registered surfaces."""
    return native_style_choices() + [(name, name) for name in CUSTOM_SURFACES]


def resolve_ui_style(name):
    if name in CUSTOM_SURFACES:
        return name, 'Fusion', name
    key = next((key for label, key in native_style_choices()
                if isinstance(name, str) and name.lower() in (label.lower(), key.lower())), 'Fusion')
    return key, key, DEFAULT_SURFACE


def apply_settings_style(settings):
    settings.ui_style, settings.qt_style, settings.surface_theme = resolve_ui_style(settings.ui_style)
    apply_style(settings.qt_style, settings.surface_theme)
