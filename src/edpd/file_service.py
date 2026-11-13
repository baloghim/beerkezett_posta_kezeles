import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .locking import workspace_lock
from .models import Capabilities, EDPDError
from .paths import directory, overlap
from .state_service import inventory
from .zip_service import ZipService, read_document


def validate_paths(source, target):
    source, target = directory(source, 'A forrásarchívum'), directory(target, 'A munkamappa')
    if overlap(source, target):
        raise EDPDError('A forrás és a cél nem lehet azonos vagy egymásba ágyazott mappa.')
    return source, target


@dataclass(frozen=True)
class ExtractionPlan:
    existing: tuple
    total: int

    @property
    def present(self):
        return len(self.existing)


def file_stamp(path):
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


class FileService:
    def __init__(self, source, target, capabilities=Capabilities(), zip_service=None):
        self.source, self.target = Path(source), Path(target)
        self.capabilities = capabilities
        self.zip = zip_service or ZipService()

    def _selected(self, selected, source, entries):
        # A kiválasztott napi csomagot a zár alatt ténylegesen újraolvassuk.
        # A többi ZIP-nél a friss méret/időbélyeggel ellenőrzött tartalomjegyzék
        # használható; a negatív ütközésvizsgálat így az összes napra kiterjed.
        current = ZipService().scan(source, dates={selected.date}, entries=entries)
        if len(current) != 1 or current[0] != selected:
            self.zip.invalidate(selected.archives)
            raise EDPDError('A napi csomag megváltozott. Frissítse a listát!')
        day = current[0]
        if day.error:
            raise EDPDError(day.error)
        return day

    def _current(self, selected, source):
        entries = self.zip.catalogue(source)
        day = self._selected(selected, source, entries)
        return [day if item.date == day.date else item for item in self.zip.scan(source, entries=entries)]

    def _existing(self, day, target):
        files = inventory(target)
        return tuple(sorted((doc.name.casefold(), file_stamp(files[doc.name.casefold()]))
                            for doc in day.documents if doc.name.casefold() in files))

    def extraction_plan(self, day):
        source, target = validate_paths(self.source, self.target)
        self._selected(day, source, self.zip.catalogue(source))
        return ExtractionPlan(self._existing(day, target), len(day.documents))

    def extract(self, day, mode='skip', *, expected_existing=None, progress=None):
        notify = progress or (lambda text, done, total: None)
        if mode not in ('skip', 'overwrite'):
            raise EDPDError('Érvénytelen kicsomagolási mód.')
        if mode == 'overwrite' and (not self.capabilities.overwrite or expected_existing is None):
            raise EDPDError('A felülíráshoz jogosultság és friss célállapotra adott jóváhagyás szükséges.')
        notify('Hálózati zárolás megszerzése…', 0, 0)
        source, target = validate_paths(self.source, self.target)
        written = skipped = 0
        with workspace_lock(target):
            validate_paths(source, target)
            notify('ZIP-ek és célállapot ellenőrzése…', 0, 0)
            entries = self.zip.catalogue(source)
            self._selected(day, source, entries)
            existing = self._existing(day, target)
            if mode == 'overwrite' and existing != expected_existing:
                raise EDPDError('A munkamappa tartalma megváltozott. Ellenőrizze, és erősítse meg újra a felülírást!')
            if mode == 'skip' and len(existing) == len(day.documents):
                return 'A kiválasztott nap dokumentumai már megtalálhatók a munkamappában.'
            # Hideg indexnél ez az összes történeti tartalomjegyzéket ellenőrzi.
            # Nélküle az időablakon kívüli névütközések nem zárhatók ki.
            days = self.zip.scan(source, entries=entries)
            if any(other.error for other in days):
                raise EDPDError('Hibás archívum miatt a fájlütközések nem ellenőrizhetők biztonságosan.')
            for doc in day.documents:
                if any(other.date != day.date and any(d.name.casefold() == doc.name.casefold()
                       and (d.crc, d.size) != (doc.crc, doc.size) for d in other.documents) for other in days):
                    raise EDPDError(f'Más napi csomag eltérő dokumentuma azonos nevet használ: {doc.name}')
            approved = dict(existing)
            total = len(day.documents) - (len(existing) if mode == 'skip' else 0)
            completed = 0
            notify('PDF-ek kicsomagolása', completed, total)
            for doc in day.documents:
                files = inventory(target)
                key = doc.name.casefold()
                destination = files.get(key, target / doc.name)
                if destination.exists() and mode == 'skip':
                    skipped += 1
                    continue
                if mode == 'overwrite':
                    stamp = file_stamp(destination) if destination.exists() else None
                    if stamp != approved.get(key):
                        raise EDPDError('A célfájl megváltozott. Erősítse meg újra a felülírást: ' + doc.name)
                data = read_document(doc)
                fd, temp = tempfile.mkstemp(prefix='.edpd-', suffix='.tmp', dir=target)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if mode == 'overwrite' and key in approved:
                        if file_stamp(destination) != approved[key]:
                            raise EDPDError('A célfájl megváltozott: ' + doc.name)
                        os.replace(temp, destination)
                    else:
                        # Új fájlt felülírási módban sem írhatunk felül véletlenül.
                        try:
                            if os.name == 'nt':
                                os.rename(temp, destination)
                            else:
                                os.link(temp, destination)
                        except FileExistsError:
                            skipped += 1
                            continue
                    written += 1
                    completed += 1
                    notify('PDF-ek kicsomagolása', completed, total)
                finally:
                    Path(temp).unlink(missing_ok=True)
        return f'{written} PDF kicsomagolva, {skipped} meglévő kihagyva.'

    def _deletion_files(self, day, source, target):
        files = inventory(target)
        if day is None:
            return files
        # A megjelenített időszakon kívüli ZIP-ek is számítanak az ütközésnél.
        # A kijelölt csomag friss, a többi tartalomjegyzék időbélyege is ellenőrzött.
        days = self._current(day, source)
        if any(other.error for other in days):
            raise EDPDError('Hibás archívum miatt a napi fájlok tulajdonosa nem állapítható meg biztonságosan.')
        names = {d.name.casefold() for d in day.documents} & set(files)
        collisions = names & {d.name.casefold() for other in days if other.date != day.date for d in other.documents}
        if collisions:
            raise EDPDError('Több naphoz tartozó fájlnevek miatt a napi törlés leállt: ' + ', '.join(sorted(collisions)))
        return {k: p for k, p in files.items() if k in names}

    def deletion_plan(self, day=None):
        if not self.capabilities.delete:
            raise EDPDError('Ebben a kiadásban a törlés tiltott.')
        source, target = validate_paths(self.source, self.target)
        return set(self._deletion_files(day, source, target))

    def delete(self, day=None, *, confirmed=False, expected_names=None):
        if not confirmed or not self.capabilities.delete:
            raise EDPDError('A törléshez jogosultság és kifejezett megerősítés szükséges.')
        source, target = validate_paths(self.source, self.target)
        with workspace_lock(target):
            validate_paths(source, target)
            files = self._deletion_files(day, source, target)
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
