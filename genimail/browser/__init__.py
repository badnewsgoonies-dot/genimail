"""Browser subsystem for embedded and managed web surfaces."""

from genimail.browser.downloads import DownloadResult, download_url_content, require_pdf_bytes
from genimail.browser.errors import (
    BrowserDownloadError,
    BrowserFeatureUnavailableError,
    BrowserNavigationError,
    BrowserRuntimeError,
)
from genimail.browser.host import BrowserController, BrowserTabHandle
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
    "BrowserTabHandle",
    "DownloadResult",
    "detect_browser_runtime",
    "download_url_content",
    "require_pdf_bytes",
]
