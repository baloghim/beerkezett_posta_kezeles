from .models import EDPDError


def inventory(target):
    result = {}
    for path in target.iterdir():
        if path.suffix.lower() == '.pdf':
            key = path.name.casefold()
            if key in result:
                raise EDPDError('Kis- és nagybetűben eltérő fájlnevek ütköznek a célmappában.')
            if not path.is_file() or path.is_symlink():
                raise EDPDError(f'A célban nem szabályos PDF-fájl található: {path.name}')
            result[key] = path
    return result


def document_status(doc, files, sizes=None):
    path = files.get(doc.name.casefold())
    if path is None:
        return 'Nincs a munkamappában'
    size = sizes[doc.name.casefold()] if sizes is not None else path.stat().st_size
    return 'A munkamappában' if size == doc.size else 'Méreteltérés / ütközés'


def day_status(day, files, sizes=None):
    if day.error:
        return 'Hibás csomag'
    states = [document_status(doc, files, sizes) for doc in day.documents]
    if any(s == 'Méreteltérés / ütközés' for s in states):
        return 'Fájlütközés'
    count = states.count('A munkamappában')
    if not count:
        return 'Nincs kicsomagolva'
    return 'Kicsomagolva' if count == len(states) else 'Részben kicsomagolva'
