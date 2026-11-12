import re
import os
import json
import hashlib
import tempfile
import time
import stat
import threading
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath

from .models import ArchiveEntry, Day, Document, EDPDError

MAX_PDF = 256 * 1024 * 1024
MAX_DAY = 2 * 1024 * 1024 * 1024
_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)', re.I)


def safe_name(info):
    name = info.filename.replace('\\', '/')
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith('/') or any(p in ('.', '..') for p in parts)
            or any(any(c in p for c in '<>:"|?*') or p.endswith((' ', '.'))
                   or any(ord(c) < 32 for c in p) or _RESERVED.match(p) for p in parts)
            or stat.S_ISLNK(info.external_attr >> 16)):
        raise EDPDError(f'Nem biztonságos ZIP-bejegyzés: {info.filename}')
    if info.file_size > MAX_PDF or info.flag_bits & 1:
        raise EDPDError(f'Túl nagy vagy titkosított PDF: {info.filename}')
    return parts[-1]


class ZipService:
    def __init__(self, cache_dir=None):
        self.cache = {}
        self.mutex = threading.RLock()
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.root = None
        self.cache_path = None
        self.dirty = False
        self.last_save = 0

    def _root(self, root):
        if self.root == root:
            return
        cache = self.cache_dir.resolve() if self.cache_dir is not None else None
        unsafe = cache is not None and (cache == root or root in cache.parents)
        if not unsafe:
            self._save(force=True)
        else:
            self.dirty = False
        self.root, self.cache, self.cache_path = root, {}, None
        if self.cache_dir is None or unsafe:
            return
        identity = str(root).casefold() if os.name == 'nt' else str(root)
        key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        self.cache_path = self.cache_dir / (key + '.json')
        try:
            if self.cache_path.stat().st_size > 128 * 1024 * 1024:
                return
            data = json.loads(self.cache_path.read_text(encoding='utf-8'))
            if data.get('schema') != 1 or data.get('root') != str(root):
                return
            loaded = {}
            for name, record in data['archives'].items():
                if '/' in name or '\\' in name or not name.lower().endswith('.zip'):
                    raise ValueError('Invalid archive name')
                payload = {k: record[k] for k in ('stamp', 'documents', 'error')}
                digest = hashlib.sha256(json.dumps([name, payload], sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
                if record.get('checksum') != digest:
                    raise ValueError('Sérült metaadat-gyorsítótár')
                stamp = tuple(record['stamp'])
                if len(stamp) != 2 or any(type(n) is not int or n < 0 for n in stamp):
                    raise ValueError('Invalid stamp')
                path = root / name
                documents = []
                for member, size, crc in record['documents']:
                    if (not isinstance(member, str) or not member.lower().endswith('.pdf')
                            or type(size) is not int or not 0 <= size <= MAX_PDF
                            or type(crc) is not int or not 0 <= crc <= 0xffffffff):
                        raise ValueError('Invalid metadata')
                    info = zipfile.ZipInfo(member)
                    info.file_size = size
                    documents.append(Document(path, member, safe_name(info), size, crc))
                error = record['error']
                if not isinstance(error, str):
                    raise ValueError('Invalid error')
                if not error:
                    loaded[path] = (stamp, tuple(documents), error)
            self.cache = loaded
        except (OSError, ValueError, TypeError, KeyError, AttributeError, EDPDError):
            self.cache = {}  # A gyorsítótár pótolható, nem üzleti állapot.
        self.dirty = False

    def _save(self, force=False):
        if not self.cache_path or not self.dirty or (not force and time.monotonic() - self.last_save < 30):
            return
        temp = None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {'schema': 1, 'root': str(self.root), 'archives': {
                p.name: {'stamp': stamp, 'documents': [(d.member, d.size, d.crc) for d in docs], 'error': error}
                for p, (stamp, docs, error) in self.cache.items() if not error}}
            for name, record in data['archives'].items():
                record['checksum'] = hashlib.sha256(json.dumps([name, record], sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
            fd, temp = tempfile.mkstemp(dir=self.cache_path.parent, prefix='.index-', suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, separators=(',', ':'))
            os.replace(temp, self.cache_path)
            self.dirty = False
            self.last_save = time.monotonic()
        except OSError:
            pass  # Nem írhatjuk felül ezzel a hálózati művelet eredményét.
        finally:
            if temp:
                try:
                    Path(temp).unlink(missing_ok=True)
                except OSError:
                    pass

    def invalidate(self, paths):
        with self.mutex:
            for path in paths:
                if self.cache.pop(path, None) is not None:
                    self.dirty = True

    def save(self):
        with self.mutex:
            self._save(force=True)

    def catalogue(self, source):
        root = Path(source).resolve(strict=True)
        entries = []
        # Windows FindFirstFile már átadja a stat-adatokat; a ZIP-eket itt nem nyitjuk meg.
        with os.scandir(root) as listing:
            for entry in listing:
                if not entry.name.lower().endswith('.zip'):
                    continue
                try:
                    day = datetime.strptime(entry.name[:8], '%Y%m%d').date()
                except ValueError:
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stamp = entry.stat(follow_symlinks=False)
                entries.append(ArchiveEntry(root / entry.name, day, stamp.st_mtime_ns, stamp.st_size))
        entries.sort(key=lambda item: (item.date, item.path.name), reverse=True)
        with self.mutex:
            self._root(root)
            known = {e.path for e in entries}
            invalid = (set(self.cache) - known) | {p for p, value in self.cache.items() if value[2]}
            for path in invalid:
                del self.cache[path]
                self.dirty = True
        return tuple(entries)

    def _read(self, entry):
        with self.mutex:
            self._root(entry.path.parent)
            cached = self.cache.get(entry.path)
            if cached and cached[0] == entry.stamp and not cached[2]:
                return cached[1], cached[2]
            documents, error = (), ''
            try:
                before = entry.path.stat()
                if (before.st_mtime_ns, before.st_size) != entry.stamp:
                    raise EDPDError('A ZIP megváltozott. Frissítse a listát!')
                with zipfile.ZipFile(entry.path) as archive:
                    documents = tuple(Document(entry.path, i.filename, safe_name(i), i.file_size, i.CRC)
                                      for i in archive.infolist()
                                      if not i.is_dir() and i.filename.lower().endswith('.pdf'))
                names = [d.name.casefold() for d in documents]
                if len(names) != len(set(names)):
                    raise EDPDError('Azonos PDF-fájlnevek ütköznek a ZIP-ben.')
                after = entry.path.stat()
                if (after.st_mtime_ns, after.st_size) != entry.stamp:
                    raise EDPDError('A ZIP megváltozott olvasás közben. Frissítse a listát!')
            except (OSError, ValueError, zipfile.BadZipFile, EDPDError) as exc:
                error = f'{entry.path.name}: {exc}'
                documents = ()
            self.cache[entry.path] = (entry.stamp, documents, error)
            self.dirty = True
            return documents, error

    def scan(self, source, history_days=None, *, today=None, dates=None, entries=None):
        if history_days not in (None, 14, 30, 90, 180):
            raise ValueError('Érvénytelen időszak')
        today = today or date.today()
        first = today - timedelta(days=history_days - 1) if history_days is not None else None
        entries = self.catalogue(source) if entries is None else entries
        grouped = {}
        for entry in entries:
            # A dátumszűrés minden ZIP-megnyitás és tartalomjegyzék-olvasás ELŐTT történik.
            if dates is not None and entry.date not in dates:
                continue
            if first is not None and not first <= entry.date <= today:
                continue
            grouped.setdefault(entry.date, []).append(entry)
        days = []
        for day, items in sorted(grouped.items(), reverse=True):
            documents, errors = [], []
            for entry in sorted(items, key=lambda e: e.path.name):
                docs, error = self._read(entry)
                documents.extend(docs)
                if error:
                    errors.append(error)
            names = [d.name.casefold() for d in documents]
            if len(names) != len(set(names)):
                errors.append('Azonos PDF-fájlnevek ütköznek a napi csomagon belül.')
            if sum(d.size for d in documents) > MAX_DAY:
                errors.append('A napi PDF-adag meghaladja a 2 GiB biztonsági korlátot.')
            days.append(Day(day, tuple(e.path for e in sorted(items, key=lambda e: e.path.name)), tuple(documents), '\n'.join(errors)))
        with self.mutex:
            self._save()
        return days

    def origin_state(self, source, files, entries):
        with self.mutex:
            self._root(Path(source).resolve(strict=True))
            pending = [e for e in entries if e.path not in self.cache or self.cache[e.path][0] != e.stamp]
            complete = not pending and not any(self.cache[e.path][2] for e in entries if e.path in self.cache)
            owners = {name: [] for name in files}
            for entry in entries:
                cached = self.cache.get(entry.path)
                if cached and cached[0] == entry.stamp and not cached[2]:
                    for doc in cached[1]:
                        if doc.name.casefold() in owners:
                            owners[doc.name.casefold()].append((entry.date, entry.path.name))
            labels = {}
            for name, matches in owners.items():
                if len(matches) > 1:
                    dates = ', '.join(sorted({d.strftime('%Y.%m.%d.') for d, _ in matches}))
                    labels[name] = f'Többértelmű: {dates} ({len(matches)} ZIP)'
                elif matches:
                    labels[name] = matches[0][0].strftime('%Y.%m.%d.') + ('' if complete else ' (ellenőrzés alatt)')
                else:
                    labels[name] = 'Ismeretlen'
            return labels, tuple(pending), complete

    def index_batch(self, entries):
        for entry in entries:
            self._read(entry)
        with self.mutex:
            self._save()


def read_document(document):
    with zipfile.ZipFile(document.archive) as archive:
        info = archive.getinfo(document.member)
        safe_name(info)
        if (info.file_size, info.CRC) != (document.size, document.crc):
            raise EDPDError('A ZIP megváltozott. Frissítse a csomaglistát!')
        return archive.read(info)
