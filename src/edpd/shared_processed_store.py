"""Shared Manager marks, stored in the workspace and serialized with PDF operations."""
import ctypes
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .file_service import validate_paths
from .locking import workspace_lock
from .models import EDPDError
from .paths import filesystem_path

MAX_STATE = 16 * 1024 * 1024
PROTECTION = 0x03  # FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_HIDDEN
REPARSE_POINT = 0x400


def shared_packet_id(day):
    payload = [day.date.isoformat(), sorted(path.name for path in day.archives),
               sorted((doc.archive.name, doc.member, doc.name, doc.size, doc.crc)
                      for doc in day.documents)]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class SharedState:
    packets: frozenset | None = None
    stamp: tuple | None = None
    error: str = ''
    recovery: tuple | None = None


class InvalidState(EDPDError):
    pass


def file_stamp(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    attributes = getattr(info, 'st_file_attributes', 0)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or attributes & REPARSE_POINT:
        raise EDPDError(f'Nem szabályos közös állomány: {path.name}')
    return info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, attributes


def read_bytes(path):
    with path.open('rb') as stream:
        data = stream.read(MAX_STATE + 1)
    if len(data) > MAX_STATE:
        raise InvalidState(f'Túl nagy állomány: {path.name}')
    return data


def read_record(path):
    raw = read_bytes(path)
    try:
        record = json.loads(raw.decode('utf-8'))
        if (not isinstance(record, dict) or type(record.get('schema')) is not int
                or record['schema'] != 2 or type(record.get('revision')) is not int
                or record['revision'] < 0 or not isinstance(record.get('updated_at'), str)):
            raise ValueError()
        timestamp = datetime.fromisoformat(record['updated_at'].replace('Z', '+00:00'))
        if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
            raise ValueError()
        packets = record.get('packets')
        if (not isinstance(packets, list)
                or any(not isinstance(key, str) or not re.fullmatch('[0-9a-f]{64}', key) for key in packets)
                or len(set(packets)) != len(packets)):
            raise ValueError()
    except (ValueError, RecursionError) as exc:
        raise InvalidState(f'Sérült vagy ismeretlen formátumú állomány: {path.name}') from exc
    return record, raw


def encode_record(revision, packets):
    return (json.dumps({
        'schema': 2,
        'revision': revision,
        'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'packets': sorted(packets),
    }, indent=2) + '\n').encode('utf-8')


def windows_attributes(path, value):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    setter = kernel.SetFileAttributesW
    setter.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32)
    setter.restype = ctypes.c_int
    if not setter(str(path), value or 0x80):  # FILE_ATTRIBUTE_NORMAL
        raise ctypes.WinError(ctypes.get_last_error())


def replace_protected(path, raw):
    if len(raw) > MAX_STATE:
        raise EDPDError('A közös feldolgozottsági állomány elérte a méretkorlátot.')
    fd, name = tempfile.mkstemp(prefix='.edpd-processed-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    previous = None
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == 'nt':
            windows_attributes(temporary, PROTECTION)
            previous = file_stamp(path)
            if previous is not None and previous[-1] & 1:
                windows_attributes(path, previous[-1] & ~1)
        try:
            os.replace(temporary, path)
        except OSError:
            if previous is not None and file_stamp(path) is not None:
                windows_attributes(path, previous[-1] | PROTECTION)
            raise
        installed = file_stamp(path)
        if os.name == 'nt' and installed is not None and installed[-1] & PROTECTION != PROTECTION:
            windows_attributes(path, installed[-1] | PROTECTION)
            installed = file_stamp(path)
        if (installed is None or (os.name == 'nt' and installed[-1] & PROTECTION != PROTECTION)
                or read_bytes(path) != raw):
            raise EDPDError(f'Az állománycsere nem ellenőrizhető: {path.name}')
    finally:
        if temporary.exists():
            if os.name == 'nt':
                windows_attributes(temporary, 0)
            temporary.unlink()


class SharedProcessedStore:
    def __init__(self, source, target):
        self.source = source
        self.target = filesystem_path(target)

    @property
    def primary(self):
        return self.target / '.edpd-processed.json'

    @property
    def backup(self):
        return self.target / '.edpd-processed.bak'

    def stamps(self):
        return file_stamp(self.primary), file_stamp(self.backup)

    def inspect(self, cached=None):
        packets = None
        try:
            stamps = self.stamps()
            if cached is not None and not cached.error and stamps == cached.stamp:
                return cached
            if stamps[0] is None:
                error = 'Hiányzik a közös feldolgozottsági állomány.'
            else:
                try:
                    primary, _ = read_record(self.primary)
                    error = ''
                except InvalidState as exc:
                    error = str(exc)
            backup = None
            backup_error = 'Hiányzik a közös biztonsági másolat.'
            if stamps[1] is not None:
                try:
                    backup, _ = read_record(self.backup)
                    backup_error = ''
                except InvalidState as exc:
                    backup_error = str(exc)
            if self.stamps() != stamps:
                raise EDPDError('A közös állapot olvasás közben változott. Próbálja újra!')
            if error:
                if backup is not None:
                    return SharedState(error=error + ' Érvényes biztonsági másolat áll rendelkezésre.',
                                       recovery=stamps)
                raise InvalidState(f'{error} {backup_error}')
            if backup is not None and backup['revision'] > primary['revision']:
                raise InvalidState('A közös állomány régebbi a biztonsági másolatnál.')
            packets = frozenset(primary['packets'])
            if backup_error:
                raise InvalidState(backup_error)
            return SharedState(packets, stamps)
        except (OSError, EDPDError) as exc:
            return SharedState(packets=packets, error=f'A közös feldolgozottsági állapot írása szünetel: {exc}')

    def prepare(self):
        """Check a newly selected workspace. Initialize only on explicit opt-in."""
        _, target = validate_paths(self.source, self.target)
        with workspace_lock(target):
            if self.stamps() == (None, None):
                initial = encode_record(0, ())
                # Preserve a usable recovery copy even if initialization is interrupted.
                replace_protected(self.backup, initial)
                replace_protected(self.primary, initial)
            else:
                # Check creation, attribute changes, and rename without replacing shared data.
                with tempfile.TemporaryDirectory(prefix='.edpd-probe-', dir=target) as folder:
                    probe = Path(folder) / 'probe'
                    try:
                        replace_protected(probe, b'EDPD')
                        replace_protected(probe, b'EDPD2')
                    finally:
                        if os.name == 'nt' and probe.exists():
                            windows_attributes(probe, 0)
                state = self.inspect()
                if state.error and state.recovery is None:
                    raise EDPDError(state.error)
                if not state.error:
                    self.protect_existing(state.stamp)

    def protect_existing(self, stamps):
        if os.name == 'nt':
            for path, stamp in zip((self.primary, self.backup), stamps):
                if stamp[-1] & PROTECTION != PROTECTION:
                    windows_attributes(path, stamp[-1] | PROTECTION)
                    if file_stamp(path)[-1] & PROTECTION != PROTECTION:
                        raise EDPDError(f'A fájlvédelem nem ellenőrizhető: {path.name}')

    def set_processed(self, key, desired):
        _, target = validate_paths(self.source, self.target)
        with workspace_lock(target):
            state = self.inspect()
            if state.error:
                raise EDPDError(state.error)
            primary, previous = read_record(self.primary)
            packets = set(primary['packets'])
            # The explicit add/remove command applies to the latest locked state.
            if (key in packets) != desired:
                if desired:
                    packets.add(key)
                else:
                    packets.discard(key)
                replace_protected(self.backup, previous)
                replace_protected(self.primary, encode_record(primary['revision'] + 1, packets))
            else:
                self.protect_existing(state.stamp)
            return self.inspect()

    def restore(self, expected):
        _, target = validate_paths(self.source, self.target)
        with workspace_lock(target):
            state = self.inspect()
            if state.recovery is None or state.recovery != expected:
                raise EDPDError('A helyreállítható állapot megváltozott. Frissítse a jelzőket!')
            _, raw = read_record(self.backup)
            if expected[0] is not None:
                diagnostic = self.target / '.edpd-processed.damaged'
                # An oversized record exceeds the bounded diagnostic copy size.
                if expected[0][1] <= MAX_STATE:
                    replace_protected(diagnostic, read_bytes(self.primary))
            replace_protected(self.primary, raw)
            return self.inspect()
