"""Staged extraction with cooperative cancellation and durable recovery records.

Call run/restore only while holding the workspace OS lock. Other applications do
not share that lock; changed files are retained instead of being blindly undone.
"""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from .models import EDPDError


class ExtractionCancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise ExtractionCancelled()


def fingerprint(path):
    if path.is_symlink() or not path.is_file():
        raise EDPDError(f'Nem szabályos helyreállítandó fájl: {path.name}')
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    stamp = lambda s: (s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino)
    if stamp(before) != stamp(after):
        raise EDPDError(f'Olvasás közben megváltozott fájl: {path.name}')
    return [*stamp(after), digest.hexdigest()]


def save_journal(folder, records):
    temporary = folder / 'journal.tmp'
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump({'schema': 1, 'records': records}, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, folder / 'journal.json')


def restore(folder, records, notify=lambda *args: None):
    errors = []
    for record in reversed(records):
        if record['state'] in ('prepared', 'restored', 'committed'):
            continue
        destination = folder.parent / record['name']
        backup = folder / record['backup'] if record['backup'] else None
        try:
            installed = record.get('installed')
            if installed is None:
                unchanged = (backup is not None and destination.exists() and fingerprint(destination) == record['before'])
                if unchanged or (backup is None and not destination.exists() and not destination.is_symlink()):
                    record['state'] = 'restored'
                    save_journal(folder, records)
                    continue
                raise EDPDError('A véglegesítés eredménye bizonytalan; kézi ellenőrzés szükséges.')
            if destination.exists() or destination.is_symlink():
                current = fingerprint(destination)
                if backup is not None and current[-1] == record['before'][-1] and current[:2] == record['before'][:2]:
                    record['state'] = 'restored'
                    save_journal(folder, records)
                    continue
                if current != installed:
                    raise EDPDError('Másik folyamat megváltoztatta; nem módosítottuk.')
            elif backup is None:
                record['state'] = 'restored'
                save_journal(folder, records)
                continue
            else:
                # A hiányzó felülírt fájl külső törlés eredménye is lehet.
                raise EDPDError('A véglegesített fájl eltűnt; kézi ellenőrzés szükséges.')
            if backup is not None:
                if fingerprint(backup)[-1] != record['before'][-1]:
                    raise EDPDError('Sérült vagy megváltozott biztonsági másolat.')
                temporary_restore = folder / (backup.name + '.restore')
                shutil.copy2(backup, temporary_restore)
                with temporary_restore.open('r+b') as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary_restore, destination)
            else:
                destination.unlink()
            record['state'] = 'restored'
            save_journal(folder, records)
        except Exception as exc:
            errors.append(f"{record['name']}: {exc}")
    if errors:
        raise EDPDError('A visszaállítás nem teljes. Megőrzött helyreállítási adatok: '
                        + str(folder) + '\n' + '\n'.join(errors))
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        raise EDPDError('A visszavonás után technikai adatok maradtak: ' + str(folder) + '\n' + str(exc)) from exc


def recover(folder, source=None, workspace=None):
    """Explicit recovery under the OS lock, using only local validated paths."""
    from .locking import workspace_lock
    folder = Path(folder).absolute()
    if folder.is_symlink() or not folder.name.startswith('.edpd-recovery-'):
        raise EDPDError('Érvénytelen helyreállítási könyvtár.')
    from .paths import overlap
    if source and overlap(folder.parent, source):
        raise EDPDError('A forrásarchívumban helyreállítás sem végezhet írást.')
    if workspace and folder.parent.resolve() != Path(workspace).resolve():
        raise EDPDError('A helyreállítási mappa nem a beállított munkamappában található.')
    with workspace_lock(folder.parent):
        data = json.loads((folder / 'journal.json').read_text(encoding='utf-8'))
        if data.get('schema') != 1 or not isinstance(data.get('records'), list):
            raise EDPDError('Érvénytelen helyreállítási napló.')
        for record in data['records']:
            name, backup = record['name'], record['backup']
            if (Path(name).name != name or '/' in name or '\\' in name or
                    not name.lower().endswith('.pdf') or name in ('.', '..') or
                    (backup is not None and (Path(backup).name != backup or not backup.endswith('.bak')))):
                raise EDPDError('Nem biztonságos naplóútvonal.')
        restore(folder, data['records'])


def run(target, documents, mode, approved, read_document, stamp, notify, cancel):
    target = Path(target)
    pending = list(target.glob('.edpd-recovery-*'))
    if pending:
        raise EDPDError('Korábbi művelet helyreállítása szükséges. Ne törölje az adatokat:\n'
                        + '\n'.join(map(str, pending)))
    if cancel is not None and cancel.is_set():
        return 'A kicsomagolás megszakítva; nem történt módosítás.'
    folder = Path(tempfile.mkdtemp(prefix='.edpd-recovery-', dir=target))
    records = []
    skipped = 0
    try:
        save_journal(folder, records)
        candidates = []
        from .state_service import inventory
        files = inventory(target)
        for doc in documents:
            key = doc.name.casefold()
            if mode == 'skip' and key in files:
                skipped += 1
                continue
            candidates.append((doc, files.get(key, target / doc.name)))
        total = len(candidates)
        notify('PDF-ek előkészítése', 0, total)
        for index, (doc, destination) in enumerate(candidates):
            check_cancel(cancel)
            data = read_document(doc)
            check_cancel(cancel)
            staged = folder / f'{index}.pdf'
            with staged.open('wb') as stream:
                for offset in range(0, len(data), 1024 * 1024):
                    check_cancel(cancel)
                    stream.write(data[offset:offset + 1024 * 1024])
                stream.flush()
                os.fsync(stream.fileno())
            backup_name = None
            before = None
            if mode == 'overwrite' and doc.name.casefold() in approved:
                if stamp(destination) != approved[doc.name.casefold()]:
                    raise EDPDError('A felülírandó célfájl megváltozott: ' + doc.name)
                before = fingerprint(destination)
                backup_name = f'{index}.bak'
                shutil.copy2(destination, folder / backup_name)
                with (folder / backup_name).open('r+b') as stream:
                    os.fsync(stream.fileno())
                if fingerprint(destination) != before or fingerprint(folder / backup_name)[-1] != before[-1]:
                    raise EDPDError('A biztonsági másolat készítése közben megváltozott fájl: ' + doc.name)
            records.append({'name': destination.name, 'staged': staged.name, 'backup': backup_name,
                            'before': before, 'installed': None, 'state': 'prepared'})
            save_journal(folder, records)
            notify('PDF-ek előkészítése', index + 1, total)
        check_cancel(cancel)
        notify('PDF-ek véglegesítése', 0, total)
        written = 0
        for index, record in enumerate(records):
            check_cancel(cancel)
            destination, staged = target / record['name'], folder / record['staged']
            if record['backup']:
                if fingerprint(destination) != record['before']:
                    raise EDPDError('A célfájl megváltozott: ' + record['name'])
            elif destination.exists() or destination.is_symlink():
                if mode == 'skip':
                    skipped += 1
                    notify('PDF-ek véglegesítése', index + 1, total)
                    continue
                raise EDPDError('Új célfájl jelent meg: ' + record['name'])
            staged_identity = fingerprint(staged)
            record['state'] = 'publishing'
            save_journal(folder, records)
            if record['backup']:
                os.replace(staged, destination)
            elif os.name == 'nt':
                os.rename(staged, destination)
            else:
                os.link(staged, destination)
                staged.unlink()
            installed = fingerprint(destination)
            if installed[-1] != staged_identity[-1] or installed[3] != staged_identity[3]:
                raise EDPDError('A véglegesített fájlt más folyamat megváltoztatta: ' + record['name'])
            record['installed'] = installed
            record['state'] = 'published'
            save_journal(folder, records)
            written += 1
            notify('PDF-ek véglegesítése', index + 1, total)
        check_cancel(cancel)
    except Exception as exc:
        notify('Megszakítás / visszaállítás folyamatban…', 0, 0)
        restore(folder, records, notify)
        if isinstance(exc, ExtractionCancelled):
            return 'A kicsomagolás megszakítva; a módosítások visszavonva.'
        raise EDPDError(str(exc) + '\nA művelet módosításait visszavontuk.') from exc

    for record in records:
        if record['state'] == 'published':
            record['state'] = 'committed'
    try:
        save_journal(folder, records)
    except OSError as exc:
        notify('Visszaállítás folyamatban…', 0, 0)
        for record in records:
            if record['state'] == 'committed':
                record['state'] = 'published'
        restore(folder, records, notify)
        raise EDPDError('A véglegesítési napló mentése sikertelen; a módosításokat visszavontuk.\n' + str(exc)) from exc
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        raise EDPDError('A PDF-ek véglegesítve, de a technikai adatok takarítása nem sikerült: ' + str(folder) + '\n' + str(exc)) from exc
    return f'{written} PDF kicsomagolva, {skipped} meglévő kihagyva.'
