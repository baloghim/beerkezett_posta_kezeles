"""Real-process startup/instance checks, shared by source tests and Windows EXE CI.

Only synthetic local folders are used. No file paths or document contents enter
reports. A new process/new profile is measured; the OS file cache is not flushed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


def read_report(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


class Harness:
    def __init__(self, command, root):
        self.command, self.root = command, root
        self.namespace = 'startup-test-' + uuid.uuid4().hex
        self.processes = []
        self.env = os.environ.copy()
        self.env['APPDATA'] = str(root / 'profile')
        self.env['LOCALAPPDATA'] = str(root / 'local-profile')
        if os.name == 'nt':
            self.env.pop('QT_QPA_PLATFORM', None)  # Real Win32 HWNDs, not offscreen placeholders.
        else:
            self.env['QT_QPA_PLATFORM'] = 'offscreen'
        for name in ('source', 'target', 'profile/EDPD'):
            (root / name).mkdir(parents=True, exist_ok=True)
        self.config = root / 'profile/EDPD/settings.json'
        self.settings()

    def settings(self, **fields):
        data = {'source': str(self.root/'source'), 'target': str(self.root/'target'),
                'refresh_minutes': 15, 'history_days': 14, **fields}
        self.config.write_text(json.dumps(data), encoding='utf-8')

    def start(self, name, *, delay=0, network_delay=0, lifetime=800, command=None, cwd=None):
        path = self.root / (name + '.json')
        before = time.perf_counter_ns()
        args = [*(command or self.command), '--startup-report', str(path),
                '--startup-exit-ms', str(lifetime), '--startup-test-namespace', self.namespace,
                '--startup-delay-ms', str(delay), '--startup-network-delay-ms', str(network_delay)]
        # Never inherit or dump user documents/settings; each harness owns an isolated profile.
        process = subprocess.Popen(args, env=self.env, cwd=cwd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE)
        self.processes.append(process)
        return process, path, before

    def wait(self, run, predicate, timeout=45):
        process, path, _ = run
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            report = read_report(path)
            if predicate(report):
                return report
            if process.poll() is not None:
                error = process.stderr.read().decode('utf-8', errors='replace')
                raise AssertionError(f'Startup process exited early ({process.returncode}): {error[-2500:]}')
            time.sleep(.025)
        raise AssertionError('Startup report timeout')

    def loaded(self, run):
        result = self.wait(run, lambda r:r.get('outcome') == 'loaded')
        result['process_to_python_entry_ms'] = round((result['entry_perf_counter_ns']-run[2])/1e6, 3)
        result['process_to_splash_ms'] = round(result['process_to_python_entry_ms']+result['events_ms']['splash_visible'], 3)
        result['process_to_main_ms'] = round(result['process_to_python_entry_ms']+result['events_ms']['main_window_visible'], 3)
        assert result['events_ms']['splash_visible'] <= result['events_ms']['main_window_visible']
        assert result['events_ms']['main_window_visible'] <= result['events_ms']['first_background_load_finished']
        return result

    def native_main_windows(self):
        if os.name != 'nt':
            return None
        import ctypes
        from ctypes import wintypes as w
        from edpd.single_instance import InstanceGuard
        guard = InstanceGuard(self.namespace)
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetPropW.argtypes = [w.HWND, w.LPCWSTR]
        user.GetPropW.restype = w.HANDLE
        user.IsWindowVisible.argtypes = [w.HWND]
        user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        callback = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        user.EnumWindows.argtypes = [callback, w.LPARAM]
        pids = []
        def inspect(hwnd, unused):
            if user.GetPropW(hwnd, guard.property_name+'.main') and user.IsWindowVisible(hwnd):
                pid = w.DWORD()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pids.append(pid.value)
            return True
        user.EnumWindows(callback(inspect), 0)
        return pids

    def finish(self, run):
        process = run[0]
        assert process.wait(timeout=45) == 0, process.stderr.read().decode('utf-8', errors='replace')
        process.stderr.close()

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if not process.stderr.closed:
                process.stderr.close()


def verify(command, root, *, copied_command=None):
    harness = Harness(command, root)
    checks, timings = [], {}
    try:
        first = harness.start('first', lifetime=3500)
        timings['new_profile_first_process'] = harness.loaded(first)
        second = harness.start('second')
        peer = harness.wait(second, lambda r:r.get('outcome') == 'secondary')
        assert peer['peer_state'] in ('main_visible', 'activation_requested'), peer
        harness.finish(second)
        assert 'qt_core_import_ms' not in peer['durations_ms']
        if os.name == 'nt':
            assert harness.native_main_windows() == [first[0].pid]
        assert first[0].poll() is None
        checks.extend(['first_new_profile_start', 'second_launch_activates_existing'])
        # Same identity from another installed copy or another working directory.
        other = root/'other-working-directory'
        other.mkdir()
        third = harness.start('other-copy', command=copied_command, cwd=other)
        assert harness.wait(third, lambda r:r.get('outcome') == 'secondary')['peer_state'] != 'initializing'
        harness.finish(third)
        if os.name == 'nt':
            assert harness.native_main_windows() == [first[0].pid]
        checks.append('different_installation_directories')
        harness.finish(first)

        # Both launches race before either imports Qt. Exactly one may enter the GUI.
        a = harness.start('rapid-a', delay=1300, lifetime=900)
        b = harness.start('rapid-b', delay=1300, lifetime=900)
        deadline = time.monotonic()+45
        while time.monotonic()<deadline:
            states = [read_report(run[1]).get('outcome') for run in (a,b)]
            if 'secondary' in states:
                break
            time.sleep(.025)
        assert states.count('secondary') == 1, states
        secondary, primary = (a,b) if states[0]=='secondary' else (b,a)
        assert read_report(secondary[1])['peer_state']=='initializing'
        harness.finish(secondary)
        timings['rapid_double_launch'] = harness.loaded(primary)
        harness.finish(primary)
        checks.extend(['rapid_double_launch_one_gui', 'second_launch_during_initialization'])

        # Delay is inside snapshot's worker, never on the UI thread.
        slow = harness.start('slow-network', network_delay=2000, lifetime=400)
        timings['slow_network_worker'] = harness.loaded(slow)
        events = timings['slow_network_worker']['events_ms']
        assert events['first_background_load_finished']-events['main_window_visible'] >= 1900
        harness.finish(slow)
        checks.append('slow_network_does_not_block_main_window')

        harness.settings(source=str(root/'unavailable-source'), target=str(root/'unavailable-target'))
        missing = harness.start('missing-network')
        assert harness.loaded(missing)['access_error']
        harness.finish(missing)
        checks.append('unavailable_network_drives')

        harness.config.write_text('{invalid configuration', encoding='utf-8')
        invalid = harness.start('invalid-config')
        assert harness.loaded(invalid)['configuration_error'] == 'JSONDecodeError'
        harness.finish(invalid)
        checks.append('invalid_settings_file')

        for theme in ('Crystal SVG','Nuvola','KDE Modern Classic','Papirus','We10X'):
            harness.settings(icon_theme=theme)
            themed = harness.start('theme-'+theme.replace(' ','-'), lifetime=150)
            result = harness.loaded(themed)
            assert result['icon_theme'] == theme
            harness.finish(themed)
        checks.append('five_saved_themes_start_in_real_processes')

        harness.settings()
        crashed = harness.start('crash', lifetime=30000)
        harness.loaded(crashed)
        crashed[0].kill()
        crashed[0].wait(timeout=10)
        restarted = harness.start('restart-after-crash', lifetime=200)
        harness.loaded(restarted)
        harness.finish(restarted)
        checks.extend(['normal_close_allows_restart','crash_does_not_leave_stale_lock'])
        return {'passed': True, 'frozen_executable': bool(copied_command), 'platform': sys.platform,
                'cache_condition': 'new processes and new profile; OS cache not flushed',
                'checks': checks, 'timings': timings}
    finally:
        harness.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    assert os.name=='nt', 'Packaged EXE verification requires Windows'
    executable=args.executable.resolve()
    with tempfile.TemporaryDirectory(prefix='edpd-startup-') as folder:
        root=Path(folder)
        copy=root/'other-installation'
        shutil.copytree(executable.parent, copy)
        report=verify([str(executable)], root, copied_command=[str(copy/executable.name)])
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'checks':report['checks'],'timings':report['timings']}))


if __name__=='__main__':
    main()
