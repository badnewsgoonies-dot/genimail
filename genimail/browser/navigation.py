import html
from urllib.parse import urlparse

from genimail.browser.errors import BrowserNavigationError


ALLOWED_SCHEMES = {"http", "https", "file", ""}


def validate_url(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        raise BrowserNavigationError("Empty URL cannot be opened.")

    parsed = urlparse(normalized)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise BrowserNavigationError(f"Blocked URL scheme: {scheme}")
    return normalized


def wrap_plain_text_as_html(text: str) -> str:
    safe = html.escape(text or "")
    return (
        "<html><body>"
        "<pre style='font-family: Segoe UI; white-space: pre-wrap; margin: 12px;'>"
        f"{safe}"
        "</pre>"
        "</body></html>"
    )

