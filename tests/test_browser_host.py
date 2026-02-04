import types

import pytest

from genimail.browser.errors import BrowserFeatureUnavailableError
from genimail.browser.host import BrowserController
from genimail.browser.runtime import BrowserRuntimeInfo, BrowserRuntimeStatus


def test_browser_controller_requires_runtime(monkeypatch):
    def fake_detect():
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.MISSING_RUNTIME,
            detail="runtime missing",
        )

    from genimail.browser import host

    monkeypatch.setattr(host, "detect_browser_runtime", fake_detect)
    controller = BrowserController(root=None)

    with pytest.raises(BrowserFeatureUnavailableError):
        controller.start(parent_frame=None)


class _FakeCore:
    def __init__(self, can_back=True, can_forward=True):
        self.CanGoBack = can_back
        self.CanGoForward = can_forward
        self.back_calls = 0
        self.forward_calls = 0
        self.reload_calls = 0

    def GoBack(self):
        self.back_calls += 1

    def GoForward(self):
        self.forward_calls += 1

    def Reload(self):
        self.reload_calls += 1


class _FakeView:
    def __init__(self, core):
        self.core = core
        self.url = "https://example.com"

    def get_url(self):
        return self.url


def test_browser_controller_navigation_helpers(monkeypatch):
    def fake_detect():
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.READY,
            detail="ok",
        )

    from genimail.browser import host

    monkeypatch.setattr(host, "detect_browser_runtime", fake_detect)
    controller = BrowserController(root=None)
    assert controller.is_initialized() is False
    core = _FakeCore(can_back=True, can_forward=False)
    controller._main_view = _FakeView(core)
    assert controller.is_initialized() is True

    assert controller.go_back() is True
    assert core.back_calls == 1
    assert controller.go_forward() is False
    assert core.forward_calls == 0
    assert controller.reload() is True
    assert core.reload_calls == 1
    assert controller.get_current_url() == "https://example.com"


def test_apply_edgechrome_compat_patch_adds_web_view_alias(monkeypatch):
    from genimail.browser import host

    class FakeEdgeChrome:
        pass

    fake_module = types.SimpleNamespace(EdgeChrome=FakeEdgeChrome)

    def fake_import_module(name):
        if name == "webview.platforms.edgechromium":
            return fake_module
        raise ImportError(name)

    monkeypatch.setattr(host.importlib, "import_module", fake_import_module)
    host._apply_edgechrome_compat_patch()

    instance = FakeEdgeChrome()
    instance.webview = "fake-control"
    assert instance.web_view == "fake-control"


def test_create_webview_raises_when_sta_mode_conflicts(monkeypatch):
    def fake_detect():
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.READY,
            detail="ok",
        )

    from genimail.browser import host

    monkeypatch.setattr(host, "detect_browser_runtime", fake_detect)
    monkeypatch.setattr(
        host,
        "ensure_sta_apartment",
        lambda: types.SimpleNamespace(ready=False, detail="mode conflict"),
    )
    controller = BrowserController(root=None)

    class _Parent:
        @staticmethod
        def winfo_width():
            return 900

        @staticmethod
        def winfo_reqwidth():
            return 900

        @staticmethod
        def winfo_height():
            return 560

        @staticmethod
        def winfo_reqheight():
            return 560

    with pytest.raises(BrowserFeatureUnavailableError):
        controller._create_webview(_Parent())
