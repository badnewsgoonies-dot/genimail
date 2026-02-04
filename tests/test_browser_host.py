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

