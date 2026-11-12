# Rögzített Python 3.10 + Qt 5.15 csomagolás. Csak Windows x64-en futtatandó.
import sys
from pathlib import Path
import PySide2
from PyInstaller.utils.hooks import collect_all

if sys.platform != 'win32' or sys.version_info[:2] != (3, 10):
    raise RuntimeError('A kiadáshoz Windows x64 és Python 3.10 szükséges.')

fitz_data, fitz_binaries, fitz_imports = collect_all('fitz')
a = Analysis(['run_edpd.py'], pathex=['src'], binaries=fitz_binaries,
             datas=fitz_data, hiddenimports=fitz_imports,
             excludes=['PySide6', 'PyQt6', 'PyQt5', 'tkinter', 'numpy'],
             noarchive=False)

# Ne szivárogjon be a modern runner System32/VS telepítésének új VC-runtime-ja.
# A PySide2 wheel saját, korabeli alkalmazáslokális DLL-jeit csomagoljuk.
qt_root = Path(PySide2.__file__).parent
vc = {p.name.lower(): str(p) for p in qt_root.glob('*.dll')
      if p.name.lower().startswith(('msvcp140', 'vcruntime140', 'concrt140', 'vcomp140', 'vcamp140', 'vccorlib140'))}
required_vc = {'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'}
if not required_vc.issubset(vc):
    raise RuntimeError('Hiányos PySide2 VC-runtime csomag.')
cleaned = []
for dest, source, kind in a.binaries:
    name = Path(dest).name.lower()
    if name == 'ucrtbase.dll' or name.startswith('api-ms-win-crt-'):
        continue  # Windows 10 saját UCRT-je; nem a runner új rendszerfájljai.
    cleaned.append((dest, vc.get(name, source), kind))
a.binaries = cleaned
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EDPD-Manager',
          debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='EDPD-Manager')
