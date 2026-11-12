import importlib.util
import shutil
import sys
from pathlib import Path
import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='Valódi Windows Qt DLL-ek szükségesek')
def test_large_qt_export_table_is_not_truncated(tmp_path):
    import PySide2
    root = Path(PySide2.__file__).parent
    # A Qt5Gui több mint 25 ezer exportja meghaladja a pefile alapértelmezett
    # exportkorlátját. A QtWidgets ezek közül későbbi nevekre is hivatkozik.
    for name in ['Qt5Gui.dll', 'Qt5Widgets.dll']:
        shutil.copyfile(root / name, tmp_path / name)
    path = Path(__file__).parent.parent / 'scripts' / 'audit_windows_binary.py'
    spec = importlib.util.spec_from_file_location('windows_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.audit(tmp_path)
    assert result['passed'], result['errors'][:5]
    assert len(result['binaries']) == 2
