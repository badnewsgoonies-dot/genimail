import ctypes

from genimail import com_runtime


def test_ensure_sta_apartment_reports_changed_mode(monkeypatch):
    class FakeOle32:
        @staticmethod
        def CoInitializeEx(_reserved, _flags):
            return com_runtime.RPC_E_CHANGED_MODE

    class FakeWindll:
        ole32 = FakeOle32()

    monkeypatch.setattr(ctypes, "windll", FakeWindll(), raising=False)
    monkeypatch.setattr(com_runtime, "_cached_status", None)

    status = com_runtime.ensure_sta_apartment()
    assert status.ready is False
    assert "RPC_E_CHANGED_MODE" in status.detail


def test_ensure_sta_apartment_reports_ready(monkeypatch):
    class FakeOle32:
        @staticmethod
        def CoInitializeEx(_reserved, _flags):
            return 0

    class FakeWindll:
        ole32 = FakeOle32()

    monkeypatch.setattr(ctypes, "windll", FakeWindll(), raising=False)
    monkeypatch.setattr(com_runtime, "_cached_status", None)

    status = com_runtime.ensure_sta_apartment()
    assert status.ready is True
