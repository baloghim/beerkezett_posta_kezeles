"""Reversible surface themes, independent of native Qt styles and icon themes."""
import weakref
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QColor, QPalette
from PySide2.QtWidgets import QApplication
import shiboken2
from .palettes import PALETTES, REQUIRED_KEYS
from .styles import stylesheet
from ...surface_styles import SURFACE_NAMES, DEFAULT_SURFACE, LUNA

THEME_NAMES = SURFACE_NAMES
DEFAULT = DEFAULT_SURFACE


class SurfaceThemeManager(QObject):
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.name = DEFAULT
        self.native_palette = None
        self.used_palette = False
        self.qt_style_name = QApplication.instance().style().objectName()

    @property
    def active(self):
        return self.name != DEFAULT

    def clear(self):
        app = QApplication.instance()
        app.setStyleSheet('')
        if self.native_palette is not None:
            app.setPalette(self.native_palette)
        self.native_palette = None

    def set_theme(self, name):
        if name not in THEME_NAMES:
            name = DEFAULT
        css = ''
        if name != DEFAULT:
            try:
                css = stylesheet(name)
                colours = PALETTES[name]
                # Validate before changing any live widget, including damaged tables.
                if not css or set(colours) != REQUIRED_KEYS or any(not QColor(value).isValid() for value in colours.values()):
                    name = DEFAULT
            except (KeyError, TypeError, ValueError):
                name = DEFAULT
        app = QApplication.instance()
        if name == DEFAULT:
            self.clear()
        else:
            if self.native_palette is None:
                self.qt_style_name = app.style().objectName() or self.qt_style_name
                self.native_palette = QPalette(app.palette())
            palette = QPalette(self.native_palette)
            for role, key in ((QPalette.Window,'window'),(QPalette.WindowText,'text'),
                              (QPalette.Base,'field'),(QPalette.AlternateBase,'alternate'),
                              (QPalette.Text,'text'),(QPalette.Button,'middle'),(QPalette.ButtonText,'text'),
                              (QPalette.Highlight,'selection'),(QPalette.HighlightedText,'text'),
                              (QPalette.Light,'shine'),(QPalette.Mid,'edge'),
                              (QPalette.ToolTipBase,'top'),(QPalette.ToolTipText,'text')):
                palette.setColor(role, QColor(colours[key]))
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor(colours['disabled']))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(colours['disabled']))
            if name == LUNA:
                palette.setColor(QPalette.HighlightedText, QColor('#ffffff'))
            app.setPalette(palette)
            app.setStyleSheet(css)
            self.used_palette = True
        self.name = name
        self.changed.emit(name)
        return name

    def prepare_style_change(self):
        previous = self.name
        self.clear()
        self.name = DEFAULT
        return previous

    def finish_style_change(self, requested):
        # After a palette override Qt does not automatically adopt a new style's
        # palette. Explicitly restore the newly selected factory style first.
        if self.used_palette:
            QApplication.instance().setPalette(QApplication.instance().style().standardPalette())
        return self.set_theme(requested)

    def subscribe(self, widget, method='refresh_surface'):
        reference = weakref.ref(widget)
        def update(*args):
            target = reference()
            if target is not None and shiboken2.isValid(target):
                getattr(target, method)()
        self.changed.connect(update)
        def disconnect(*args):
            try:
                self.changed.disconnect(update)
            except (RuntimeError, TypeError):
                pass
        widget.destroyed.connect(disconnect)


_manager = None


def manager():
    global _manager
    if _manager is None:
        _manager = SurfaceThemeManager()
    return _manager


def set_theme(name):
    return manager().set_theme(name)
