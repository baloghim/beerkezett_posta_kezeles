import os
import tempfile
from pathlib import Path

from .locking import workspace_lock
from .models import Capabilities, EDPDError
from .state_service import inventory
from .zip_service import ZipService, read_document


def validate_paths(source, target):
    source, target = Path(source).resolve(strict=True), Path(target).resolve(strict=True)
    if not source.is_dir() or not target.is_dir():
        raise EDPDError('A forrásnak és a célnak létező mappának kell lennie.')
    # samefile kezeli a Windows meghajtóbetű/UNC aliasokat is.
    if (any(source.samefile(p) for p in (target, *target.parents))
            or any(target.samefile(p) for p in (source, *source.parents))):
        raise EDPDError('A forrás és a cél nem lehet azonos vagy egymásba ágyazott mappa.')
    return source, target


class FileService:
    def __init__(self, source, target, capabilities=Capabilities()):
        self.source, self.target = Path(source), Path(target)
        self.capabilities = capabilities

    def _current(self, selected):
        # Zárolás után újraolvasás, nem a felület elavult listájára támaszkodunk.
        days = ZipService().scan(self.source)
        day = next((d for d in days if d.date == selected.date), None)
        if day is None or day != selected:
            raise EDPDError('A napi csomag megváltozott. Frissítse a listát!')
        if day.error:
            raise EDPDError(day.error)
        return days

    def extract(self, day, mode='skip'):
        if mode not in ('skip', 'overwrite'):
            raise EDPDError('Érvénytelen kicsomagolási mód.')
        if mode == 'overwrite' and not self.capabilities.overwrite:
            raise EDPDError('Ebben a kiadásban a felülírás tiltott.')
        source, target = validate_paths(self.source, self.target)
        written = skipped = 0
        with workspace_lock(target):
            validate_paths(source, target)
            days = self._current(day)
            for doc in day.documents:
                if any(other.date != day.date and any(d.name.casefold() == doc.name.casefold()
                       and (d.crc, d.size) != (doc.crc, doc.size) for d in other.documents) for other in days):
                    raise EDPDError(f'Más napi csomag eltérő dokumentuma azonos nevet használ: {doc.name}')
            for doc in day.documents:
                files = inventory(target)
                destination = files.get(doc.name.casefold(), target / doc.name)
                if destination.exists() and mode == 'skip':
                    skipped += 1
                    continue
                data = read_document(doc)  # ZIP CRC-ellenőrzés is történik.
                fd, temp = tempfile.mkstemp(prefix='.edpd-', suffix='.tmp', dir=target)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if mode == 'overwrite':
                        os.replace(temp, destination)
                    else:
                        # Hard link atomikusan, felülírás nélkül. SMB/NTFS támogatja;
                        # nem támogatott fájlrendszeren biztonságosan hibával leáll.
                        try:
                            if os.name == 'nt':
                                os.rename(temp, destination)
                            else:
                                os.link(temp, destination)
                        except FileExistsError:
                            skipped += 1
                            continue
                    written += 1
                finally:
                    Path(temp).unlink(missing_ok=True)
        return f'{written} PDF kicsomagolva, {skipped} meglévő kihagyva.'

    def delete(self, day=None, *, confirmed=False, expected_names=None):
        if not confirmed or not self.capabilities.delete:
            raise EDPDError('A törléshez jogosultság és kifejezett megerősítés szükséges.')
        source, target = validate_paths(self.source, self.target)
        with workspace_lock(target):
            validate_paths(source, target)
            files = inventory(target)
            if day is not None:
                days = self._current(day)
                if any(other.error for other in days):
                    raise EDPDError('Hibás archívum miatt a napi fájlok tulajdonosa nem állapítható meg biztonságosan.')
                names = {d.name.casefold() for d in day.documents}
                collisions = names & {d.name.casefold() for other in days if other.date != day.date for d in other.documents}
                if collisions:
                    raise EDPDError('Több naphoz tartozó fájlnevek miatt a napi törlés leállt: ' + ', '.join(sorted(collisions)))
                files = {k: p for k, p in files.items() if k in names}
            if expected_names is None or set(files) != set(expected_names):
                raise EDPDError('A munkamappa tartalma megváltozott. Ellenőrizze, és erősítse meg újra a törlést!')
            errors, removed = [], 0
            for path in files.values():
                try:
                    path.unlink()
                    removed += 1
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    errors.append(f'{path.name}: {exc}')
            if errors:
                raise EDPDError(f'{removed} PDF törölve; a többi nem törölhető:\n' + '\n'.join(errors))
        return f'{removed} PDF törölve a munkamappából.'
