import os
from pathlib import Path
from uuid import UUID
from PySide2.QtCore import QSaveFile, QIODevice, QStandardPaths
from .models import EDPDError
from .paths import directory, overlap


def documents_directory():
    if os.name != 'nt':
        return QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

    import ctypes
    from ctypes import wintypes

    # GUID memory layout and the current user's configured path, even if offline.
    folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(
        UUID('FDD39AD0-238F-46AF-ADB4-6C85480369C7').bytes_le)
    get_path = ctypes.windll.shell32.SHGetKnownFolderPath
    get_path.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE,
                         ctypes.POINTER(ctypes.c_void_p))
    get_path.restype = ctypes.c_long
    free_path = ctypes.windll.ole32.CoTaskMemFree
    free_path.argtypes = (ctypes.c_void_p,)
    free_path.restype = None
    dont_verify = 0x4000  # KF_FLAG_DONT_VERIFY
    result = ctypes.c_void_p()
    try:
        if get_path(folder_id, dont_verify, None, ctypes.byref(result)) == 0 and result.value:
            return ctypes.wstring_at(result.value)
        return ''
    finally:
        if result.value:
            free_path(result)


def accessible_save_directory(value):
    path = directory(value, 'A PDF-mentési mappa')
    try:
        with os.scandir(path):
            pass
    except OSError as exc:
        raise EDPDError(f'A PDF-mentési mappa nem érhető el: {value}\n{exc}') from exc
    return path


def check_pdf_save_directory(settings):
    if not settings.default_pdf_save_dir:
        return
    path = accessible_save_directory(settings.default_pdf_save_dir)
    for folder in (settings.source, getattr(settings, 'target', None)):
        if not folder:
            continue
        protected = Path(folder).resolve()
        if protected == path or protected in path.parents:
            raise EDPDError('A PDF-mentési mappa legyen a forrásarchívumon és a munkamappán kívül.')
        try:
            protected_stat = protected.stat()
        except FileNotFoundError:
            continue
        if any(os.path.samestat(protected_stat, parent.stat()) for parent in (path, *path.parents)):
            raise EDPDError('A PDF-mentési mappa legyen a forrásarchívumon és a munkamappán kívül.')


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
