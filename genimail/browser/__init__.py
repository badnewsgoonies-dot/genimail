"""Browser subsystem for embedded and managed web surfaces."""

from genimail.browser.errors import (
    BrowserDownloadError,
    BrowserFeatureUnavailableError,
    BrowserNavigationError,
    BrowserRuntimeError,
)
from genimail.browser.host import BrowserController
from genimail.browser.runtime import (
    BrowserRuntimeInfo,
    BrowserRuntimeStatus,
    detect_browser_runtime,
)

__all__ = [
    "BrowserController",
    "BrowserDownloadError",
    "BrowserFeatureUnavailableError",
    "BrowserNavigationError",
    "BrowserRuntimeError",
    "BrowserRuntimeInfo",
    "BrowserRuntimeStatus",
    "detect_browser_runtime",
]
