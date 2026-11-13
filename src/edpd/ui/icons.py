from pathlib import Path
from PySide2.QtGui import QIcon

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def icon(name):
    result = QIcon()
    for size in (22, 32, 48, 64, 128, 256):
        path = ASSETS / 'icons' / str(size) / (name + '.png')
        if path.is_file():
            result.addFile(str(path))
    return result
