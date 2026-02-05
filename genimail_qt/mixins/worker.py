from PySide6.QtWidgets import QMessageBox

from genimail_qt.workers import Worker


class WorkerMixin:
    def _submit(self, fn, on_result, on_error=None):
        worker = Worker(fn)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._on_worker_error)
        self.thread_pool.start(worker)

    def _on_worker_error(self, trace_text):
        if hasattr(self, "connect_btn"):
            self.connect_btn.setEnabled(True)
        if hasattr(self, "_set_status"):
            self._set_status("Operation failed")
        QMessageBox.critical(self, "Operation Error", trace_text)


__all__ = ["WorkerMixin"]
