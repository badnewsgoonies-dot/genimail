from genimail.errors import ExternalServiceError


class BrowserRuntimeError(ExternalServiceError):
    """Base browser subsystem error."""


class BrowserFeatureUnavailableError(BrowserRuntimeError):
    """Raised when browser features are unavailable on this machine."""


class BrowserNavigationError(BrowserRuntimeError):
    """Raised for invalid or failed navigation requests."""


class BrowserDownloadError(BrowserRuntimeError):
    """Raised for download failures in browser-driven flows."""


__all__ = [
    "BrowserDownloadError",
    "BrowserFeatureUnavailableError",
    "BrowserNavigationError",
    "BrowserRuntimeError",
]
