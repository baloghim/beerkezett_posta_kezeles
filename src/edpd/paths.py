"""Windows-meghajtók és UNC-utak lexikai, adatvesztés nélküli kezelése."""
import ntpath
import os
import re
from pathlib import Path
from .models import EDPDError


def normalize_path(value):
    value = str(value).strip()
    if re.match(r'^[A-Za-z]:', value) or value.startswith(('\\\\', '//')):
        # ntpath megőrzi az UNC és a \\?\UNC előtagot, a H://a//b alakot javítja.
        return ntpath.normpath(value.replace('/', '\\'))
    return os.path.normpath(value) if value else ''


def filesystem_path(value):
    text = normalize_path(value)
    if not text:
        raise EDPDError('A mappaútvonal nem lehet üres.')
    windows = bool(re.match(r'^[A-Za-z]:', text) or text.startswith('\\\\'))
    if windows and (os.name != 'nt' or not ntpath.isabs(text)):
        raise EDPDError(f'A Windows hálózati útvonal ezen a rendszeren nem érhető el: {text}')
    path = Path(text)
    if os.name == 'nt' and not path.is_absolute():
        raise EDPDError('Teljes meghajtóbetűjeles vagy UNC-útvonal szükséges.')
    return path


def directory(value, label):
    try:
        path = filesystem_path(value).resolve(strict=True)
        if not path.is_dir():
            raise OSError('Nem mappa')
        return path
    except OSError as exc:
        raise EDPDError(f'{label} nem érhető el, vagy nincs olvasási jogosultság: {value}\n{exc}') from exc


def overlap(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    if a == b or a in b.parents or b in a.parents:
        return True
    # A még nem létező állapotmappa meglévő őse is lehet a forrás másik
    # meghajtóbetűjeles aliasa. Létrehozás előtt ezt is ki kell zárni.
    for root, child in ((a, b), (b, a)):
        try:
            reference = root.stat()
        except FileNotFoundError:
            continue
        for ancestor in (child, *child.parents):
            try:
                if os.path.samestat(reference, ancestor.stat()):
                    return True
            except FileNotFoundError:
                continue
    return False
