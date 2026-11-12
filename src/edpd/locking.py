import os
from contextlib import contextmanager
from .models import EDPDError


@contextmanager
def workspace_lock(target, *, filename='.edpd-operation.lock', label='munkamappa'):
    """SMB-n is közös OS fájlzár; összeomláskor az operációs rendszer oldja fel.

    A technikai fájlt tilos törölni: a név újralétrehozása megkerülné a zárat.
    """
    if filename not in ('.edpd-operation.lock', '.edpd-marks.lock'):
        raise ValueError('Ismeretlen zárolási fájl.')
    path = target / filename
    if path.is_symlink():
        raise EDPDError('A zárolási fájl nem lehet hivatkozás.')
    stream = open(path, 'a+b')
    locked = False
    try:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise EDPDError(f'A(z) {label} foglalt, vagy a hálózati zárolás nem érhető el. Próbálja újra!') from exc
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
