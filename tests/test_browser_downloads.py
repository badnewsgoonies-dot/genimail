import pytest

from genimail.browser.downloads import DownloadResult, download_url_content, require_pdf_bytes
from genimail.browser.errors import BrowserDownloadError


class _FakeResponse:
    def __init__(self, content=b"", content_type="application/pdf", status_code=200):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_require_pdf_bytes_accepts_pdf_signature():
    result = DownloadResult(
        success=True,
        url="https://example.com/x.pdf",
        content=b"%PDF-1.4 body",
        content_type="application/octet-stream",
    )
    assert require_pdf_bytes(result).startswith(b"%PDF")


def test_require_pdf_bytes_rejects_non_pdf():
    result = DownloadResult(
        success=True,
        url="https://example.com/notpdf",
        content=b"<html>nope</html>",
        content_type="text/html",
    )
    with pytest.raises(BrowserDownloadError):
        require_pdf_bytes(result)


def test_download_url_content(monkeypatch):
    from genimail.browser import downloads

    def fake_get(url, allow_redirects, timeout):
        assert url == "https://example.com/doc.pdf"
        assert allow_redirects is True
        assert timeout
        return _FakeResponse(content=b"%PDF-1.7", content_type="application/pdf", status_code=200)

    monkeypatch.setattr(downloads.requests, "get", fake_get)
    result = download_url_content("https://example.com/doc.pdf")

    assert result.success is True
    assert result.status_code == 200
    assert result.content == b"%PDF-1.7"

