"""Közös kézi jelölések: önálló, zárolt és atomikusan cserélt JSON."""
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from .locking import workspace_lock
from .models import Capabilities, EDPDError
from .paths import filesystem_path, overlap
from .file_service import validate_paths
from .zip_service import ZipService


def day_identity(day):
    # Nem meghajtóbetűjel: ugyanazt az archívumot más betűjelen is látják.
    packages = [(p.name.casefold(), sorted((d.member, d.size, d.crc)
                 for d in day.documents if d.archive == p)) for p in day.archives]
    raw = json.dumps([day.date.isoformat(), sorted(packages)], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def validate_shared_directory(value, source, target):
    source, target = validate_paths(source, target)
    if not str(value).strip():
        raise EDPDError('Adja meg a közös állapotmappát a Beállításokban!')
    shared = filesystem_path(value).resolve()
    if overlap(shared, source) or overlap(shared, target):
        raise EDPDError('A közös állapotmappa legyen különálló: nem lehet a forrás vagy a munkamappa része, illetve szülőmappája.')
    return shared


class CompletionStore:
    def __init__(self, directory, source, target, capabilities=Capabilities(), zip_service=None):
        self.directory, self.source, self.target = directory, source, target
        self.capabilities = capabilities
        self.index = zip_service

    def _load(self, directory):
        path = directory / 'completed.json'
        if path.is_symlink():
            raise EDPDError('A közös állapotfájl nem lehet hivatkozás.')
        try:
            with path.open('r', encoding='utf-8') as stream:
                data = json.load(stream)
        except FileNotFoundError:
            if directory.is_dir() or directory.parent.is_dir():
                return set()
            raise EDPDError(f'A közös állapotmappa nem érhető el: {directory}')
        except (OSError, ValueError) as exc:
            raise EDPDError(f'A közös állapotfájl nem olvasható; a jelölések nem módosíthatók.\n{exc}') from exc
        if (not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('done'), dict)
                or any(not re.fullmatch('[0-9a-f]{64}', k) or v is not True for k, v in data['done'].items())):
            raise EDPDError('A közös állapotfájl sérült vagy ismeretlen verziójú. Nem írjuk felül.')
        return set(data['done'])

    def read(self):
        directory = validate_shared_directory(self.directory, self.source, self.target)
        # Atomikus csere miatt az olvasó a teljes régi vagy új állapotot látja.
        return self._load(directory)

    def set_done(self, day, done):
        if not self.capabilities.mark_done:
            raise EDPDError('Ebben a kiadásban az Elvégezve jelölés nem módosítható.')
        if type(done) is not bool or day.error:
            raise EDPDError('Hibás napi csomag nem jelölhető elvégzettnek.')
        directory = validate_shared_directory(self.directory, self.source, self.target)
        directory.mkdir(parents=True, exist_ok=True)
        directory = validate_shared_directory(directory, self.source, self.target)
        with workspace_lock(directory, filename='.edpd-marks.lock', label='közös állapotfájl'):
            current = ZipService().scan(self.source, dates={day.date})
            if len(current) != 1 or current[0] != day:
                if self.index is not None:
                    self.index.invalidate(day.archives)
                raise EDPDError('A napi csomag megváltozott. Frissítse a listát!')
            marks = self._load(directory)  # Kötelező újraolvasás a közös zár alatt.
            key = day_identity(day)
            marks.add(key) if done else marks.discard(key)
            fd, temp = tempfile.mkstemp(dir=directory, prefix='.completed-', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump({'schema': 1, 'done': {k: True for k in sorted(marks)}}, stream, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                for attempt in range(4):
                    try:
                        os.replace(temp, directory / 'completed.json')
                        break
                    except OSError as exc:
                        # Rövid Windows/SMB olvasási megnyitás nem feltétlenül
                        # engedi a törlési megosztást. A régi fájl ekkor ép marad.
                        if getattr(exc, 'winerror', None) not in (32, 33) or attempt == 3:
                            raise
                        time.sleep(0.05 * 2 ** attempt)
            finally:
                Path(temp).unlink(missing_ok=True)
        return 'Elvégezve jelölés mentve.' if done else 'Elvégezve jelölés visszavonva.'
