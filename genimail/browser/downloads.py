from dataclasses import dataclass

import requests

from genimail.browser.errors import BrowserDownloadError
from genimail.constants import HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC


@dataclass(frozen=True)
class DownloadResult:
    success: bool
    url: str
    content: bytes | None = None
    content_type: str | None = None
    status_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    local_path: str | None = None


def download_url_content(
    url: str,
    timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC),
    allow_redirects: bool = True,
) -> DownloadResult:
    try:
        response = requests.get(url, allow_redirects=allow_redirects, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BrowserDownloadError(f"Download failed: {exc}") from exc

    return DownloadResult(
        success=True,
        url=url,
        content=response.content or b"",
        content_type=(response.headers.get("Content-Type") or "").lower(),
        status_code=response.status_code,
    )


def require_pdf_bytes(result: DownloadResult) -> bytes:
    if not result.success or result.content is None:
        raise BrowserDownloadError("No content available.")

    content = result.content
    content_type = (result.content_type or "").lower()
    is_pdf = content.startswith(b"%PDF") or "application/pdf" in content_type
    if not is_pdf:
        raise BrowserDownloadError("Link did not return a PDF file.")
    return content

