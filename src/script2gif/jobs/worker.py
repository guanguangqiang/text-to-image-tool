from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str, str)
    progress = Signal(int, int, str)
    finished = Signal()


class FunctionWorker(QRunnable):
    """Run a blocking function outside the GUI thread.

    Set ``with_progress=True`` to pass a callback named ``progress`` into the
    function. The callback accepts ``current, total, message``.
    """

    def __init__(
        self,
        function: Callable[..., Any],
        *args: Any,
        with_progress: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.with_progress = with_progress
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                self.kwargs["progress"] = self.signals.progress.emit
            result = self.function(*self.args, **self.kwargs)
        except Exception as exc:
            self.signals.failed.emit(str(exc), traceback.format_exc())
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
