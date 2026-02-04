import html
import re
from urllib.parse import urlparse

from genimail.browser.errors import BrowserNavigationError


ALLOWED_SCHEMES = {"http", "https", "file", ""}
LIGHT_PREVIEW_STYLE = (
    "<meta name='color-scheme' content='light'>"
    "<meta name='supported-color-schemes' content='light'>"
    "<style id='genimail-light-preview-style'>"
    ":root{color-scheme:light !important;}"
    "html,body{background:#ffffff !important;color:#1f2937 !important;}"
    "body{margin:12px;font-family:'Segoe UI',Arial,sans-serif;line-height:1.35;}"
    "a{color:#0b57d0 !important;}"
    "img{max-width:100%;height:auto;}"
    "</style>"
)


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
        "<html><head>"
        f"{LIGHT_PREVIEW_STYLE}"
        "</head><body>"
        "<pre style='font-family: Segoe UI; white-space: pre-wrap; margin: 12px;'>"
        f"{safe}"
        "</pre>"
        "</body></html>"
    )


def ensure_light_preview_html(content: str) -> str:
    html_content = content or ""
    lowered = html_content.lower()
    if "genimail-light-preview-style" in lowered:
        return html_content

    if "<head" in lowered:
        return re.sub(
            r"(<head[^>]*>)",
            rf"\1{LIGHT_PREVIEW_STYLE}",
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )

    if "<html" in lowered:
        return re.sub(
            r"(<html[^>]*>)",
            rf"\1<head>{LIGHT_PREVIEW_STYLE}</head>",
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )

    return (
        "<html><head>"
        f"{LIGHT_PREVIEW_STYLE}"
        "</head><body>"
        f"{html_content}"
        "</body></html>"
    )
