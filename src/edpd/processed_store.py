"""Local workstation/user marks, deliberately separate from shared workspaces."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from .config import settings_path
from .locking import workspace_lock
from .models import EDPDError, Capabilities
from .paths import overlap, normalize_path


def packet_id(source, day):
    root = os.path.abspath(normalize_path(source))
    if os.name == 'nt':
        root = root.casefold()
    payload = [root, day.date.isoformat(), sorted(p.name for p in day.archives),
               sorted((d.name, d.size, d.crc) for d in day.documents)]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode('utf-8')).hexdigest()


class ProcessedStore:
    def __init__(self, source, target, capabilities=Capabilities()):
        self.capabilities = capabilities
        self.source = Path(source).resolve()
        base = Path(os.environ.get('LOCALAPPDATA', str(settings_path().parent.parent))) / 'EDPD' / 'local-state'
        if overlap(base, source) or overlap(base, target):
            raise EDPDError('A helyi feldolgozási állapot nem kerülhet a forrásba vagy a munkamappába.')
        self.path = base / 'processed.json'

    def read(self):
        if not self.path.exists():
            return set()
        if self.path.is_symlink() or self.path.stat().st_size > 16 * 1024 * 1024:
            raise EDPDError('Érvénytelen helyi feldolgozási állomány.')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('schema') != 1 or
                not isinstance(data.get('packets'), list) or
                any(not isinstance(k, str) or len(k) != 64 or any(c not in '0123456789abcdef' for c in k)
                    for k in data['packets'])):
            raise EDPDError('Sérült helyi Feldolgozva állomány; nem írjuk felül.')
        return set(data['packets'])

    def set_processed(self, day, desired):
        if not self.capabilities.processed:
            raise EDPDError('Ebben a kiadásban a feldolgozási jelölés tiltott.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with workspace_lock(self.path.parent):
            values = self.read()
            key = packet_id(self.source, day)
            values.add(key) if desired else values.discard(key)
            fd, temporary = tempfile.mkstemp(prefix='.processed-', dir=self.path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump({'schema': 1, 'packets': sorted(values)}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                Path(temporary).unlink(missing_ok=True)
