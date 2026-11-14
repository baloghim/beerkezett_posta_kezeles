"""Run the frozen Windows application with both surfaces and fractional Qt scaling."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from edpd import __version__
from edpd.ui.themes.styles import stylesheet
import hashlib


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('executable',type=Path)
    parser.add_argument('--default-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    assert os.name=='nt','A frozen Windows EXE is required'
    base=json.loads(args.default_report.read_text(encoding='utf-8'))
    assert base['passed'] and base['host']['frozen'] and len(base['checks'])==20
    base_dpr=base['surface_validation']['device_pixel_ratio']
    css={name:hashlib.sha256(stylesheet(name).encode()).hexdigest() for name in ('Longhorn Blue','Longhorn Slate')}
    assert base['surface_validation']['css_sha256']==css
    args.output.mkdir(parents=True,exist_ok=True)
    result={'passed':False,'version':__version__,'scaling_method':'Qt environment scaling; Windows desktop setting unchanged',
            'base_device_pixel_ratio':base_dpr,'css_sha256':css,'cases':[]}
    for name,surface,scale in [('blue','Longhorn Blue','1'),('slate','Longhorn Slate','1'),
                                ('blue-125','Longhorn Blue','1.25'),('blue-150','Longhorn Blue','1.5')]:
        report=args.output/(name+'.json')
        env=os.environ.copy()
        env['QT_QPA_PLATFORM']='windows'
        env['QT_SCALE_FACTOR']=scale
        env['QT_SCALE_FACTOR_ROUNDING_POLICY']='PassThrough'
        process=subprocess.Popen([str(args.executable.resolve()),'--self-test','--self-test-surface',surface,
                                  '--report',str(report.resolve())],env=env)
        try:
            code=process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill();process.wait();raise AssertionError('Surface EXE self-test timeout: '+name)
        data=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
        assert code==0 and data.get('passed'),json.dumps(data,ensure_ascii=False)
        assert data['application_version']==__version__ and data['host']['frozen']
        assert data['requested_surface_theme']==surface and len(data['checks'])==20
        validation=data['surface_validation']
        assert validation['css_sha256']==css
        assert validation['default_palette_restored'] and validation['pdf_pixels_preserved']
        assert validation['widget_growth']<=1
        assert abs(validation['device_pixel_ratio']-base_dpr*float(scale))<.05,validation['device_pixel_ratio']
        result['cases'].append({'name':name,'surface':surface,'scale_factor':scale,
                               'device_pixel_ratio':validation['device_pixel_ratio'],'checks':len(data['checks']),
                               'report':report.name})
        print(json.dumps(result['cases'][-1]),flush=True)
    result['passed']=True
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
