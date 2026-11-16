"""Real Manager + Viewer processes and viewer second-launch activation."""
import argparse
import json
from pathlib import Path
import tempfile
from check_startup import Harness


def verify(manager_command, viewer_command, root):
    manager = Harness(manager_command, root)
    viewer = Harness(viewer_command, root)
    # Distinct identities exactly as the production applications use.
    manager.namespace, viewer.namespace = 'manager-v1', 'viewer-v1'
    folder = root/'profile/EDPD-Betekinto'
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'settings.json').write_text(json.dumps({'source':str(root/'source')}), encoding='utf-8')
    try:
        first = manager.start('manager', lifetime=8000)
        manager.loaded(first)
        other = viewer.start('viewer', lifetime=5000)
        viewer.loaded(other, 'EDPD Betekintő')
        assert first[0].poll() is None and other[0].poll() is None
        if __import__('os').name == 'nt':
            assert manager.native_main_windows()==[first[0].pid]
            assert viewer.native_main_windows()==[other[0].pid]
        second = viewer.start('viewer-second')
        peer = viewer.wait(second, lambda r:r.get('outcome')=='secondary')
        assert peer['peer_state'] in ('main_visible','activation_requested'), peer
        viewer.finish(second)
        assert other[0].poll() is None
        viewer.finish(other)
        manager.finish(first)
        return {'passed':True, 'checks':['manager_and_viewer_visible_together',
                'viewer_second_launch_activates_existing', 'clean_shutdown']}
    finally:
        viewer.close();manager.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manager',type=Path,required=True)
    parser.add_argument('--viewer',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='edpd-dual-startup-') as tmp:
        result=verify([str(args.manager.resolve())],[str(args.viewer.resolve())],Path(tmp))
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
