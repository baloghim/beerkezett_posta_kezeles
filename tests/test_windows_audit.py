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
    for name in ['Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll', *[p.name for p in root.glob('*.dll') if p.name.lower().startswith(('msvcp', 'concrt', 'vcomp', 'vcamp', 'vccorlib'))]]:
        shutil.copyfile(root / name, tmp_path / name)
    # A frozen buildhez hasonlóan a Python saját C-runtime-ját használjuk.
    for name in ['vcruntime140.dll', 'vcruntime140_1.dll']:
        candidates = [Path(sys.base_prefix) / name, Path(sys.base_prefix) / 'DLLs' / name]
        shutil.copyfile(next(p for p in candidates if p.exists()), tmp_path / name)
    path = Path(__file__).parent.parent / 'scripts' / 'audit_windows_binary.py'
    spec = importlib.util.spec_from_file_location('windows_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.audit(tmp_path)
    assert result['passed'], result['errors'][:5]
    assert len(result['binaries']) >= 6
    (tmp_path / 'concrt140.dll').unlink()
    result = module.audit(tmp_path)
    assert not result['passed']
    assert any('concrt140.dll' in error.lower() for error in result['errors'])
