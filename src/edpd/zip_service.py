import re
import stat
import threading
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from .models import Day, Document, EDPDError

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
    def __init__(self):
        self.cache = {}
        self.mutex = threading.Lock()

    def scan(self, source):
        """Csak metaadatot olvas; egy hibás nap nem rejti el a többit."""
        with self.mutex:
            grouped = {}
            seen = set()
            for path in Path(source).resolve(strict=True).iterdir():
                if path.suffix.lower() != '.zip' or not path.is_file():
                    continue
                try:
                    day = datetime.strptime(path.name[:8], '%Y%m%d').date()
                except ValueError:
                    continue
                grouped.setdefault(day, []).append(path)
            days = []
            for day, paths in sorted(grouped.items(), reverse=True):
                documents, errors = [], []
                for path in sorted(paths):
                    seen.add(path)
                    try:
                        stamp = path.stat()
                        key = (stamp.st_mtime_ns, stamp.st_size)
                        if path not in self.cache or self.cache[path][0] != key:
                            with zipfile.ZipFile(path) as archive:
                                docs = tuple(Document(path, i.filename, safe_name(i), i.file_size, i.CRC)
                                             for i in archive.infolist()
                                             if not i.is_dir() and i.filename.lower().endswith('.pdf'))
                            self.cache[path] = (key, docs)
                        documents.extend(self.cache[path][1])
                    except (OSError, ValueError, zipfile.BadZipFile, EDPDError) as exc:
                        errors.append(f'{path.name}: {exc}')
                names = [d.name.casefold() for d in documents]
                if len(names) != len(set(names)):
                    errors.append('Azonos PDF-fájlnevek ütköznek a napi csomagon belül.')
                if sum(d.size for d in documents) > MAX_DAY:
                    errors.append('A napi PDF-adag meghaladja a 2 GiB biztonsági korlátot.')
                days.append(Day(day, tuple(sorted(paths)), tuple(documents), '\n'.join(errors)))
            self.cache = {p: v for p, v in self.cache.items() if p in seen}
            return days


def read_document(document):
    with zipfile.ZipFile(document.archive) as archive:
        info = archive.getinfo(document.member)
        safe_name(info)
        if (info.file_size, info.CRC) != (document.size, document.crc):
            raise EDPDError('A ZIP megváltozott. Frissítse a csomaglistát!')
        return archive.read(info)
