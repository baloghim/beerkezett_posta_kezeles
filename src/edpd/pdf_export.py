from pathlib import Path
from PySide2.QtCore import QSaveFile, QIODevice
from .models import EDPDError
from .paths import overlap


def target_stamp(path):
    path = Path(path)
    if path.is_symlink():
        raise EDPDError('A mentési cél nem lehet hivatkozás.')
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


def validate_export(path, source=None, workspace=None):
    path = Path(path)
    if path.is_symlink():
        raise EDPDError('A mentési cél nem lehet hivatkozás.')
    for folder in (source, workspace):
        if folder and overlap(path, folder):
            raise EDPDError('A PDF mentési célja legyen a forrásarchívumon és a munkamappán kívül.')
    return path.resolve()


def save_pdf(data, path, source=None, workspace=None, expected=None, protected=()):
    path = validate_export(path, source, workspace)
    for folder in protected:
        validate_export(path, folder)
    if target_stamp(path) != expected:
        raise EDPDError('A mentési cél megváltozott. Erősítse meg újra a mentést!')
    output = QSaveFile(str(path))
    output.setDirectWriteFallback(False)
    if not output.open(QIODevice.WriteOnly):
        raise EDPDError(output.errorString())
    try:
        for start in range(0, len(data), 1024 * 1024):
            block = data[start:start + 1024 * 1024]
            if output.write(block) != len(block):
                raise EDPDError(output.errorString())
        validate_export(path, source, workspace)
        for folder in protected:
            validate_export(path, folder)
        if target_stamp(path) != expected:
            raise EDPDError('Mentés közben megváltozott a célfájl; nem írtuk felül.')
        if not output.commit():
            raise EDPDError(output.errorString())
    except Exception:
        output.cancelWriting()
        raise
