"""Verify the built Windows EXE resources and bundled Crystal PNGs."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import pefile


def verify(bundle, source):
    ico=(source/'edpd.ico').read_bytes()
    count=struct.unpack_from('<H',ico,4)[0]
    expected={}
    for i in range(count):
        w,h,_,_,_,_,size,offset=struct.unpack_from('<BBBBHHII',ico,6+16*i)
        expected[w or 256]=ico[offset:offset+size]
    pe=pefile.PE(str(bundle/'EDPD-Manager.exe'))
    resources={}
    for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        for name in kind.directory.entries:
            for language in name.directory.entries:
                data=language.data.struct
                resources[kind.id,name.id]=pe.get_data(data.OffsetToData,data.Size)
    groups=[data for (kind,_),data in resources.items() if kind==14]
    assert groups,'No RT_GROUP_ICON in EXE'
    verified=set()
    for data in groups:
        for i in range(struct.unpack_from('<H',data,4)[0]):
            w,h,_,_,planes,bits,size,resource_id=struct.unpack_from('<BBBBHHIH',data,6+14*i)
            width=w or 256
            actual=resources[3,resource_id]
            assert width in expected and actual==expected[width],f'Wrong EXE icon frame {width}'
            verified.add(width)
    assert verified=={16,24,32,48,64,128,256},verified
    packaged=bundle/'_internal/edpd/assets'
    files=list(source.rglob('*.png'))+[source/'edpd.ico',source/'manifest.json']
    for path in files:
        target=packaged/path.relative_to(source)
        assert target.is_file(),target
        assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest(),target
    return {'passed':True,'ico_sizes':sorted(verified),'asset_files':len(files)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();result=verify(args.bundle,Path(__file__).resolve().parents[1]/'src/edpd/assets')
    args.report.write_text(json.dumps(result,indent=2));print(json.dumps(result))
