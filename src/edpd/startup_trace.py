"""Timing-only startup diagnostics: never include paths, PDF data or raw errors."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path


class StartupTrace:
    def __init__(self, started_ns, report=None):
        self.started_ns = started_ns
        self.report = Path(report) if report else None
        self.metrics = {}
        self.events = {}
        self.fields = {}
        self.lock = threading.Lock()

    def elapsed(self):
        return (time.perf_counter_ns() - self.started_ns) / 1_000_000

    def add(self, name, duration_ms):
        with self.lock:
            self.metrics.setdefault(name, round(duration_ms, 3))

    def mark(self, name):
        with self.lock:
            self.events.setdefault(name, round(self.elapsed(), 3))

    def publish(self, outcome='running', **fields):
        from . import __version__
        with self.lock:
            self.fields.update(fields)
            data = {'schema': 1, 'version': __version__, 'entry_perf_counter_ns': self.started_ns,
                    'pid': os.getpid(), 'outcome': outcome, 'durations_ms': dict(self.metrics),
                    'events_ms': dict(self.events), **self.fields}
        path = self.report
        if path is None:
            base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
            if not base:
                return
            path = Path(base) / 'EDPD' / 'startup-last.json'
        def write():
            temporary = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.startup-')
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(data, stream, indent=2)
                os.replace(temporary, path)
            except OSError:
                pass  # Diagnostics must never prevent startup.
            finally:
                if temporary:
                    Path(temporary).unlink(missing_ok=True)
        if self.report:
            write()
        else:
            threading.Thread(target=write, daemon=True).start()
