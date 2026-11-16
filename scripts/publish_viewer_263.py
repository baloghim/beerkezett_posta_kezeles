"""Append a verified viewer build to the existing 2.6.3 release, never overwrite."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

REPO = 'baloghim/beerkezett_posta_kezeles'
TAG = 'v2.6.3'
ASSET = 'EDPD-Betekinto-Windows-x64.zip'


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def api(path):
    return json.loads(gh('api', f'repos/{REPO}/{path}'))


def verify_bundle(folder, commit):
    package = folder / ASSET
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    assert (folder/(ASSET+'.sha256')).read_text(encoding='utf-8-sig').split()[0] == digest
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        base = 'EDPD-Betekinto/'
        assert archive.read(base+'SOURCE-COMMIT.txt').decode('utf-8-sig').strip() == commit
        assert base+'EDPD-Betekinto.exe' in archive.namelist()
        assert base+'_internal/python310.dll' in archive.namelist()
        for name in ('viewer-native-dependencies.json', 'viewer-icon-audit.json'):
            assert json.loads(archive.read(base+name))['passed']
        for index in range(4):
            report = json.loads(archive.read(base+f'viewer-selftest-{index}.json'))
            assert report['passed'] and report['host']['frozen']
            assert report['host']['system'] == 'Windows'
            assert report['application_version'] == '2.6.3' and len(report['checks']) >= 15
    return digest


def publish(folder, run_id, commit):
    run = api(f'actions/runs/{run_id}')
    assert run['status'] == 'completed' and run['conclusion'] == 'success'
    assert run['head_sha'] == commit and run['head_branch'] == 'main'
    assert run['path'] == '.github/workflows/windows-build.yml'
    digest = verify_bundle(folder, commit)
    before = api(f'releases/tags/{TAG}')
    original_tag = api(f'git/ref/tags/{TAG}')['object']['sha']
    names = {asset['name']: asset for asset in before['assets']}
    protected = {name: names[name] for name in ('EDPD-Manager-Windows-x64.zip',
                                               'EDPD-Manager-Windows-x64.zip.sha256')}
    existing = ASSET in names or ASSET+'.sha256' in names
    if existing:
        # Resume validation after a completed upload without replacing either file.
        assert ASSET in names and ASSET+'.sha256' in names, 'Incomplete existing viewer upload'
        assert names[ASSET]['digest'] == 'sha256:'+digest, 'Different viewer ZIP exists; refusing overwrite'
        checksum_digest = hashlib.sha256((folder/(ASSET+'.sha256')).read_bytes()).hexdigest()
        assert names[ASSET+'.sha256']['digest'] == 'sha256:'+checksum_digest
    else:
        # No --clobber: existing assets are never replaced.
        gh('release', 'upload', TAG, str(folder/ASSET), str(folder/(ASSET+'.sha256')), '--repo', REPO)
    after = api(f'releases/tags/{TAG}')
    uploaded = {asset['name']: asset for asset in after['assets']}
    assert uploaded[ASSET]['digest'] == 'sha256:'+digest
    for name, original in protected.items():
        assert all(uploaded[name][key] == original[key] for key in ('id', 'size', 'digest', 'updated_at'))
    assert api(f'git/ref/tags/{TAG}')['object']['sha'] == original_tag
    previous_body = before['body'].replace('\r\n', '\n').replace('\\n', '\n')
    header = f'[**EDPD Menedzser 2.6.3 – Windows x64**](https://github.com/{REPO}/releases/download/{TAG}/EDPD-Manager-Windows-x64.zip)'
    if previous_body.startswith(header) and commit in previous_body and '\n\n---\n\n' in previous_body:
        previous_body = previous_body.split('\n\n---\n\n', 1)[1]
    notes = f'''[**EDPD Menedzser 2.6.3 – Windows x64**](https://github.com/{REPO}/releases/download/{TAG}/EDPD-Manager-Windows-x64.zip)

[**EDPD Betekintő 2.6.3 – Windows x64**](https://github.com/{REPO}/releases/download/{TAG}/{ASSET})

A Menedzser a teljes dokumentumkezelő alkalmazás. A Betekintő a napi ZIP-eket és a bennük lévő PDF-eket böngészi, nyomtatja és egyenként menti; munkamappát nem használ. A két program önállóan és egymás mellett is futtatható.

Betekintő forráscommit: [`{commit}`](https://github.com/{REPO}/commit/{commit}). A Betekintő az eredeti v2.6.3 tag után készült; a tag és az eredeti Menedzser ZIP változatlan.

[Sikeres Windows build és funkcionális ellenőrzések]({run['html_url']}) · [Betekintő használati útmutató](https://github.com/{REPO}/blob/{commit}/docs/BETEKINTO.md)

Windows: 201 sikeres forrásteszt; négy felületi témával összesen 60 sikeres Betekintő EXE-önellenőrzés; a két EXE együttfutása és a második Betekintő-indítás aktiválása sikeres. A Menedzser funkcionális, skálázási és indítási regressziói is sikeresek.

Betekintő ZIP SHA-256: `{digest}`. Mindkét ZIP mellett külön `.sha256` fájl található. Windows 10 1607 x64 technológiai alap: Python 3.10.11 / Qt 5.15.2 / PyMuPDF 1.23.26. A tényleges 1607-es célgépes próba külön szükséges.

---

'''+previous_body
    with tempfile.TemporaryDirectory(prefix='edpd-release-notes-') as tmp:
        path = Path(tmp)/'notes.md'
        with path.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(notes)
        gh('release', 'edit', TAG, '--repo', REPO, '--notes-file', str(path))
    assert api(f'releases/tags/{TAG}')['body'].replace('\r\n', '\n') == notes
    print(json.dumps({'published': True, 'source_commit': commit, 'sha256': digest,
                      'release': before['html_url'], 'build': run['html_url']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    publish(args.folder, args.run_id, args.commit)
