from genimail_qt.helpers import worker_manager as worker_manager_module


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, payload):
        for callback in list(self._callbacks):
            callback(payload)


class _Signals:
    def __init__(self):
        self.result = _Signal()
        self.error = _Signal()


class _FakeWorker:
    def __init__(self, fn):
        self.fn = fn
        self.signals = _Signals()


class _ThreadPool:
    def start(self, worker):
        try:
            payload = worker.fn()
            worker.signals.result.emit(payload)
        except Exception as exc:
            worker.signals.error.emit(f"{type(exc).__name__}: {exc}")


def test_submit_routes_result_callback_exceptions_to_error_handler(monkeypatch):
    monkeypatch.setattr(worker_manager_module, "Worker", _FakeWorker)
    manager = worker_manager_module.WorkerManager(_ThreadPool(), parent=None)
    errors = []

    def _on_result(_payload):
        raise RuntimeError("result callback failed")

    manager.submit(lambda: {"ok": True}, _on_result, errors.append)

    assert len(errors) == 1
    assert "RuntimeError" in errors[0]
    assert "result callback failed" in errors[0]
