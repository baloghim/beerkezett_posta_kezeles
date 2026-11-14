"""Logical, cached internal icons. The EDPD application identity stays fixed."""
import json
import weakref
from pathlib import Path
from PySide2.QtCore import QObject, Signal
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication, QStyle, QMenu
import shiboken2

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
THEME_NAMES = tuple(json.loads((ASSETS / 'themes.json').read_text(encoding='utf-8'))['themes'])
ALIASES = {'delete_day':'delete','clear_workdir':'clear','pdf_save':'save','pdf_print':'print',
           'first_page':'first','prev_page':'previous','next_page':'next','last_page':'last',
           'fit_width':'width','fit_page':'page','zip_item':'zip','pdf_item':'pdf','info':'about'}
STANDARD = {'extract':QStyle.SP_ArrowDown,'delete':QStyle.SP_TrashIcon,'clear':QStyle.SP_DialogDiscardButton,
            'refresh':QStyle.SP_BrowserReload,'settings':QStyle.SP_FileDialogDetailedView,
            'about':QStyle.SP_MessageBoxInformation,'warning':QStyle.SP_MessageBoxWarning,
            'first':QStyle.SP_MediaSkipBackward,'previous':QStyle.SP_ArrowLeft,
            'next':QStyle.SP_ArrowRight,'last':QStyle.SP_MediaSkipForward,
            'save':QStyle.SP_DialogSaveButton}


class IconThemeManager(QObject):
    changed = Signal(str)

    def __init__(self, root=ASSETS):
        super().__init__()
        self.root = Path(root)
        self.name = 'Crystal SVG'
        self.cache = {}
        self.sources = {}
        self.manifest = json.loads((self.root / 'themes.json').read_text(encoding='utf-8'))

    def set_theme(self, name):
        record = self.manifest['themes'].get(name)
        if name not in THEME_NAMES or (name != 'Crystal SVG' and
                (record is None or not (self.root / 'themes' / record['id']).is_dir())):
            name = 'Crystal SVG'
        if self.name != name:
            self.name = name
            self.cache = {k:v for k,v in self.cache.items() if k == 'app'}
            self.sources = {k:v for k,v in self.sources.items() if k == 'app'}
            self.changed.emit(name)
        return name

    def icon(self, name):
        role = ALIASES.get(name, name)
        if role in self.cache:
            return self.cache[role]
        result = QIcon()
        source = self.name
        if role == 'app':
            paths = [self.root / 'icons' / str(size) / 'app.png' for size in (22,32,48,64,128,256)]
            source = 'EDPD fixed application icon'
        else:
            record = self.manifest['themes'].get(self.name, {})
            paths = []
            if self.name != 'Crystal SVG' and role in record.get('icons', {}):
                paths = [self.root / 'themes' / record['id'] / str(size) / (role + '.png') for size in (22,40)]
            if not any(path.is_file() for path in paths):
                source = 'Crystal SVG'
                paths = [self.root / 'icons' / str(size) / (role + '.png') for size in (22,32,48)]
        for path in paths:
            if path.is_file():
                result.addFile(str(path))
        if result.isNull() and QApplication.instance() is not None:
            source = 'Qt standard'
            result = QApplication.instance().style().standardIcon(STANDARD.get(role, QStyle.SP_FileIcon))
        self.cache[role], self.sources[role] = result, source
        return result

    def subscribe(self, widget, method='refresh_icons'):
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
        _manager = IconThemeManager()
    return _manager


def icon(name):
    return manager().icon(name)


def set_theme(name):
    return manager().set_theme(name)


class ThemedMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        manager().subscribe(self)

    def refresh_icons(self):
        for action in self.actions():
            role = action.property('icon_role')
            if role:
                action.setIcon(icon(role))
