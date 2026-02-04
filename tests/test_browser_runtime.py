import sys
import types

from genimail.browser.runtime import (
    BrowserRuntimeStatus,
    detect_browser_runtime,
)


def test_detect_browser_runtime_ready(monkeypatch):
    fake_module = types.SimpleNamespace(have_runtime=lambda: True)
    monkeypatch.setitem(sys.modules, "tkwebview2", fake_module)

    info = detect_browser_runtime()
    assert info.status == BrowserRuntimeStatus.READY


def test_detect_browser_runtime_missing(monkeypatch):
    fake_module = types.SimpleNamespace(have_runtime=lambda: False)
    monkeypatch.setitem(sys.modules, "tkwebview2", fake_module)

    info = detect_browser_runtime()
    assert info.status == BrowserRuntimeStatus.MISSING_RUNTIME


def test_detect_browser_runtime_init_failed(monkeypatch):
    class BrokenModule:
        @staticmethod
        def have_runtime():
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "tkwebview2", BrokenModule)

    info = detect_browser_runtime()
    assert info.status == BrowserRuntimeStatus.INIT_FAILED


def test_detect_browser_runtime_uses_submodule_fallback(monkeypatch):
    from genimail.browser import runtime

    class RootModule:
        pass

    class SubModule:
        @staticmethod
        def have_runtime():
            return True

    def fake_import(name):
        if name == "tkwebview2":
            return RootModule()
        if name == "tkwebview2.tkwebview2":
            return SubModule()
        raise ImportError(name)

    monkeypatch.setattr(runtime.importlib, "import_module", fake_import)
    info = detect_browser_runtime()
    assert info.status == BrowserRuntimeStatus.READY
