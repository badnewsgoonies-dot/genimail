import pytest

from genimail.browser.errors import BrowserNavigationError
from genimail.browser.navigation import ensure_light_preview_html, validate_url, wrap_plain_text_as_html


def test_validate_url_accepts_https():
    assert validate_url("https://example.com/path") == "https://example.com/path"


def test_validate_url_blocks_script_scheme():
    with pytest.raises(BrowserNavigationError):
        validate_url("javascript:alert('x')")


def test_wrap_plain_text_as_html_escapes_input():
    html = wrap_plain_text_as_html("<b>Hello</b>")
    assert "&lt;b&gt;Hello&lt;/b&gt;" in html
    assert "genimail-light-preview-style" in html


def test_ensure_light_preview_html_injects_style():
    html = ensure_light_preview_html("<html><body><p>Hello</p></body></html>")
    assert "genimail-light-preview-style" in html
    assert "color-scheme" in html


def test_ensure_light_preview_html_is_idempotent():
    first = ensure_light_preview_html("<html><body><p>Hello</p></body></html>")
    second = ensure_light_preview_html(first)
    assert second.count("genimail-light-preview-style") == 1
