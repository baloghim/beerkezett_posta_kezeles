"""PE-függőségleltár és néhány ismert 1607 utáni API tiltása.

Ez statikus ellenőrzés; nem Windows 1607 futtatási bizonyíték.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import pefile

# Csak közvetlen/delay importokra alkalmazható; GetProcAddress ágakat nem bizonyít.
POST_1607 = {
    'VirtualAlloc2', 'VirtualAlloc2FromApp', 'MapViewOfFile3', 'MapViewOfFile3FromApp',
    'UnmapViewOfFile2', 'GetTempPath2A', 'GetTempPath2W', 'GetMachineTypeAttributes',
    'SetProcessDpiAwarenessContext', 'GetDpiFromDpiAwarenessContext',
    'GetWindowDpiHostingBehavior', 'SetThreadDpiHostingBehavior', 'GetUserDefaultGeoName',
}


def audit(root):
    entries, errors, exports = [], [], {}
    for path in sorted(root.rglob('*')):
        if path.suffix.lower() not in {'.exe', '.dll', '.pyd'}:
            continue
        pe = pefile.PE(str(path), fast_load=True, max_symbol_exports=1_000_000)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                                              pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT'],
                                              pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
        exports[path] = {symbol.name.decode('ascii', errors='replace') if symbol.name else f'ordinal:{symbol.ordinal}'
                         for symbol in getattr(getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None), 'symbols', [])}
        imports = {}
        for group in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT'):
            for descriptor in getattr(pe, group, []):
                dll = descriptor.dll.decode('ascii', errors='replace')
                symbols = [i.name.decode('ascii', errors='replace') if i.name else f'ordinal:{i.ordinal}'
                           for i in descriptor.imports]
                imports.setdefault(dll, []).extend(symbols)
                for symbol in set(symbols) & POST_1607:
                    errors.append(f'{path.relative_to(root)}: 1607 utáni API: {dll}!{symbol}')
        if pe.FILE_HEADER.Machine != 0x8664:
            errors.append(f'{path.relative_to(root)}: nem x64 PE')
        minimum = [pe.OPTIONAL_HEADER.MajorSubsystemVersion, pe.OPTIONAL_HEADER.MinorSubsystemVersion]
        if tuple(minimum) > (10, 0):
            errors.append(f'{path.relative_to(root)}: túl új PE subsystem: {minimum}')
        if 'qt6' in path.name.lower() or 'pyside6' in path.name.lower():
            errors.append(f'{path.relative_to(root)}: Qt 6 szennyeződés')
        if path.name.lower() == 'ucrtbase.dll' or path.name.lower().startswith('api-ms-win-crt-'):
            errors.append(f'{path.relative_to(root)}: a Windows 10 saját UCRT-je helyett csomagolt rendszer-DLL')
        if sys.platform == 'win32' and path.name.lower().startswith(('msvcp140', 'vcruntime140', 'concrt140', 'vcomp140', 'vcamp140', 'vccorlib140')):
            import PySide2
            trusted = Path(PySide2.__file__).parent / path.name
            if not trusted.exists() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(trusted.read_bytes()).digest():
                errors.append(f'{path.relative_to(root)}: nem a rögzített Qt wheel VC-runtime-ja')
        entries.append({'path' : path.relative_to(root).as_posix(), 'minimum_subsystem': minimum,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'imports': imports})
        pe.close()
    for entry in entries:
        for dll, symbols in entry['imports'].items():
            owner = root / entry['path']
            candidates = [(path, names) for path, names in exports.items() if path.name.casefold() == dll.casefold()]
            local = [names for path, names in candidates if path.parent == owner.parent]
            if local:
                available = local[0]
            elif candidates:
                available = candidates[0][1]
                if any(names != available for _, names in candidates):
                    errors.append(f"{entry['path']}: többértelmű csomagolt DLL: {dll}")
                    continue
            else:
                available = None
            if available is not None:
                for symbol in symbols:
                    if not symbol.startswith('ordinal:') and symbol not in available:
                        errors.append(f"{entry['path']}: hiányzó import: {dll}!{symbol}")
    if not entries:
        errors.append('Nem található natív bináris.')
    return {'passed': not errors, 'errors': errors, 'binaries': entries,
            'proves_windows1607_runtime': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"PE audit: {len(result['binaries'])} fájl, {len(result['errors'])} hiba")
    for error in result['errors'][:20]:
        print(error)
    raise SystemExit(0 if result['passed'] else 1)
