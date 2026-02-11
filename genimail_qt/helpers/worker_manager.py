from collections.abc import Callable
import traceback

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMessageBox, QWidget

from genimail_qt.workers import Worker


class WorkerManager:
    def __init__(
        self,
        thread_pool: QThreadPool,
        parent: QWidget,
        on_default_error: Callable[[str], None] | None = None,
    ) -> None:
        self.thread_pool = thread_pool
        self.parent = parent
        self.on_default_error = on_default_error

    def submit(
        self,
        fn: Callable[[], object],
        on_result: Callable[[object], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        active_error_handler = on_error or self._on_worker_error

        def _handle_result(payload: object) -> None:
            try:
                on_result(payload)
            except Exception:
                active_error_handler(traceback.format_exc())

        worker = Worker(fn)
        worker.signals.result.connect(_handle_result)
        worker.signals.error.connect(active_error_handler)
        self.thread_pool.start(worker)

    def _on_worker_error(self, trace_text: str) -> None:
        if self.on_default_error is not None:
            self.on_default_error(trace_text)
        QMessageBox.critical(self.parent, "Operation Error", trace_text)


__all__ = ["WorkerManager"]
