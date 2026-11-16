"""Release publication must resume safely and never replace existing assets."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def publisher(tmp_path, monkeypatch):
    path=Path(__file__).resolve().parents[1]/'scripts/publish_viewer_263.py'
    spec=importlib.util.spec_from_file_location('publish_viewer_263',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    commit='a'*40;digest='b'*64
    (tmp_path/(module.ASSET+'.sha256')).write_bytes(b'checksum\r\n')
    assets=[{'name':name,'id':i,'size':100,'digest':'sha256:old','updated_at':'original'}
            for i,name in enumerate(('EDPD-Manager-Windows-x64.zip','EDPD-Manager-Windows-x64.zip.sha256'))]
    assets.extend([{'name':module.ASSET,'digest':'sha256:'+digest},
                   {'name':module.ASSET+'.sha256','digest':'sha256:'+hashlib.sha256(b'checksum\r\n').hexdigest()}])
    release={'assets':assets,'body':'Original manager notes.\r\n','html_url':'https://github.com/example/release'}
    run={'status':'completed','conclusion':'success','head_sha':commit,'head_branch':'main',
         'path':'.github/workflows/windows-build.yml','html_url':'https://github.com/example/build'}
    calls=[]
    def api(path):
        if path.startswith('actions/'):return copy.deepcopy(run)
        if path.startswith('git/'):return {'object':{'sha':'original-tag'}}
        return copy.deepcopy(release)
    def gh(*args):
        calls.append(args)
        assert args[:2]==('release','edit'), 'Existing assets must never be uploaded/replaced'
        text=Path(args[args.index('--notes-file')+1]).read_text(encoding='utf-8')
        release['body']=text.replace('\n','\r\n')
        return ''
    monkeypatch.setattr(module,'api',api);monkeypatch.setattr(module,'gh',gh)
    monkeypatch.setattr(module,'verify_bundle',lambda *a:digest)
    return module,tmp_path,commit,release,run,calls


def test_resume_keeps_assets_and_handles_windows_line_endings(publisher):
    module,folder,commit,release,run,calls=publisher
    original=copy.deepcopy(release['assets'])
    module.publish(folder,123,commit)
    module.publish(folder,123,commit)
    assert release['assets']==original and len(calls)==2
    assert release['body'].count('[**EDPD Betekintő 2.6.3 – Windows x64**]')==1
    assert release['body'].endswith('Original manager notes.\r\n')


def test_refuse_existing_different_viewer_zip(publisher):
    module,folder,commit,release,run,calls=publisher
    release['assets'][2]['digest']='sha256:different'
    with pytest.raises(AssertionError,match='refusing overwrite'):module.publish(folder,123,commit)
    assert not calls


def test_refuse_build_from_other_commit(publisher):
    module,folder,commit,release,run,calls=publisher
    run['head_sha']='c'*40
    with pytest.raises(AssertionError):module.publish(folder,123,commit)
    assert not calls
