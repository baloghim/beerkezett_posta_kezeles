from PySide2.QtCore import QObject, Signal, QRunnable


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()
    progress = Signal(str, int, int)


class Job(QRunnable):
    def __init__(self, function, with_progress=False):
        super().__init__()
        self.function = function
        self.with_progress = with_progress
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function(self.signals.progress.emit) if self.with_progress else self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


