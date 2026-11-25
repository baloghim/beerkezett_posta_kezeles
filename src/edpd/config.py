import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from .paths import normalize_path
from .surface_styles import CUSTOM_SURFACES, LUNA


@dataclass
class Settings:
    source: str = 'H:\\PostaEDPB\\10_Komárom-Esztergom megye'
    target: str = 'G:\\Igazgatas\\DMS_One\\00_t_meghajtóról érkezők'
    refresh_minutes: int = 15
    history_days: int | None = 14
    geometry: str = ''
    panels: str = ''
    left_panels: str = ''
    qt_style: str = ''
    icon_theme: str = 'SE98'
    surface_theme: str = 'Alapértelmezett'
    ui_style: str = ''

    def __post_init__(self):
        # A fresh Manager profile has no native style to migrate.
        if not isinstance(self.ui_style, str) or not self.ui_style:
            if type(self) is Settings and self.qt_style == '' and self.surface_theme == 'Alapértelmezett':
                self.surface_theme = LUNA
            if self.surface_theme in CUSTOM_SURFACES:
                self.ui_style = self.surface_theme
            else:
                self.ui_style = self.qt_style if isinstance(self.qt_style, str) else 'Fusion'
        if not isinstance(self.surface_theme, str):
            self.surface_theme = 'Alapértelmezett'
        if not isinstance(self.qt_style, str) or (type(self) is Settings and not self.qt_style):
            self.qt_style = 'Fusion'
        for key in ('source', 'target') if hasattr(self, 'target') else ('source',):
            value = getattr(self, key)
            if not isinstance(value, str):
                raise ValueError('Érvénytelen mappaútvonal.')
            setattr(self, key, normalize_path(value))

    @classmethod
    def load(cls, path=None):
        path = path or default_settings_path(cls)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('A beállításfájl nem JSON-objektum.')
        if cls is Settings:
            # Preserve the previous fallbacks when an existing file lacks these fields.
            if data.get('qt_style', '') == '':
                data['qt_style'] = 'Fusion'
            data.setdefault('icon_theme', 'Crystal SVG')
        allowed = cls.__dataclass_fields__
        result = cls(**{k: v for k, v in data.items() if k in allowed})
        if not isinstance(result.surface_theme, str):
            result.surface_theme = 'Alapértelmezett'
        if (type(result.refresh_minutes) is not int or
                result.refresh_minutes not in range(5, 61, 5) or
                (result.history_days is not None and (type(result.history_days) is not int or result.history_days not in (14, 30, 90, 180))) or
                any(not isinstance(getattr(result, key), str) for key in allowed if key not in ('refresh_minutes', 'history_days'))):
            raise ValueError('Érvénytelen beállításfájl.')
        return result

    def save(self, path=None):
        path = path or default_settings_path(type(self))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.settings-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def settings_path():
    return Path(os.environ.get('APPDATA', str(Path.home() / '.config'))) / 'EDPD' / 'settings.json'


def cache_directory():
    # A nagyobb metaadat-index ne a roaming közös profilját terhelje.
    return Path(os.environ.get('LOCALAPPDATA', str(settings_path().parent.parent))) / 'EDPD' / 'zip-index'


def default_settings_path(cls):
    return viewer_settings_path() if cls is ViewerSettings else settings_path()


def viewer_settings_path():
    return settings_path().parent.parent / 'EDPD-Betekinto' / 'settings.json'


def viewer_cache_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(settings_path().parent.parent))) / 'EDPD-Betekinto' / 'zip-index'


@dataclass
class ViewerSettings:
    # Deliberately no workspace field, including when loading a manager profile.
    source: str = Settings.__dataclass_fields__['source'].default
    refresh_minutes: int = 15
    history_days: int | None = 14
    geometry: str = ''
    panels: str = ''
    left_panels: str = ''
    qt_style: str = 'Fusion'
    icon_theme: str = 'Crystal SVG'
    surface_theme: str = 'Alapértelmezett'
    ui_style: str = ''

    __post_init__ = Settings.__post_init__
    load = classmethod(Settings.load.__func__)
    save = Settings.save
