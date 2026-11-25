import importlib.util
import os
from pathlib import Path
import sys


def test_real_process_startup_races_crashes_and_network_delays(tmp_path, monkeypatch):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('check_startup', root/'scripts/check_startup.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('PYTHONPATH',str(root/'src'))
    result=module.verify([sys.executable,'-m','edpd.main'], tmp_path)
    assert result['passed'] and len(result['checks'])==12
    assert {'surface_Alapértelmezett','surface_Longhorn Blue','surface_Longhorn Slate','surface_Windows XP Luna Blue','ui_Windows XP Luna Blue'}<=set(result['timings'])
    assert 'main_modules_pdf_print_import_ms' in result['timings']['new_profile_first_process']['durations_ms']


def test_trace_never_records_paths_or_document_data(tmp_path):
    import json
    import time
    from edpd.startup_trace import StartupTrace
    trace=StartupTrace(time.perf_counter_ns(),tmp_path/'timing.json')
    trace.add('settings_load_ms',4.5)
    trace.publish('visible',configuration_error='JSONDecodeError')
    trace.mark('first_background_load_finished')
    trace.publish('loaded')
    data=json.loads((tmp_path/'timing.json').read_text())
    assert data['configuration_error']=='JSONDecodeError'
    assert str(tmp_path) not in json.dumps(data)


def test_explicit_trace_retries_when_the_reader_locks_the_report(tmp_path, monkeypatch):
    import json
    import time
    from edpd import startup_trace

    path = tmp_path / 'timing.json'
    trace = startup_trace.StartupTrace(time.perf_counter_ns(), path)
    trace.publish('visible')
    real_replace = startup_trace.os.replace
    attempts = []

    def temporarily_locked(source, destination):
        attempts.append(destination)
        if len(attempts) == 1:
            raise PermissionError('Report is open in the reader')
        real_replace(source, destination)

    monkeypatch.setattr(startup_trace.os, 'replace', temporarily_locked)
    trace.publish('loaded')
    assert attempts == [path, path]
    assert json.loads(path.read_text(encoding='utf-8'))['outcome'] == 'loaded'
    assert list(tmp_path.iterdir()) == [path]
