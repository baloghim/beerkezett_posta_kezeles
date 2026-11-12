"""Parancs futtatása eredeti kilépési kóddal és nyilvános CI-hibaösszefoglalóval.

Csak teszthez/csomagoláshoz használjuk; környezeti változót vagy titkot nem dumpol.
"""
import subprocess
import sys


def main():
    process = subprocess.run(sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             encoding='utf-8', errors='replace')
    print(process.stdout, end='')
    if process.returncode:
        tail = process.stdout[-12000:]
        for start in range(0, len(tail), 4000):
            message = tail[start:start + 4000].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=Build vagy teszt hibája::{message}')
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
