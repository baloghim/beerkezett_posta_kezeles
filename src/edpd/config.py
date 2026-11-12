import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Settings:
    source: str = 'H:\\PostaEDPB\\10_Komárom-Esztergom megye'
    target: str = 'G:\\Igazgatas\\DMS_One\\00_t_meghajtóról érkezők'
    refresh_minutes: int = 15
    geometry: str = ''
    panels: str = ''
    left_panels: str = ''

    @classmethod
    def load(cls, path=None):
        path = path or settings_path()
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('A beállításfájl nem JSON-objektum.')
        allowed = cls.__dataclass_fields__
        result = cls(**{k: v for k, v in data.items() if k in allowed})
        if (type(result.refresh_minutes) is not int or
                result.refresh_minutes not in range(5, 61, 5) or
                any(not isinstance(getattr(result, key), str) for key in allowed if key != 'refresh_minutes')):
            raise ValueError('Érvénytelen beállításfájl.')
        return result

    def save(self, path=None):
        path = path or settings_path()
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
