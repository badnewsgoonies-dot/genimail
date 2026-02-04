import pytest

from genimail.browser.errors import BrowserNavigationError
from genimail.browser.navigation import validate_url, wrap_plain_text_as_html


def test_validate_url_accepts_https():
    assert validate_url("https://example.com/path") == "https://example.com/path"


def test_validate_url_blocks_script_scheme():
    with pytest.raises(BrowserNavigationError):
        validate_url("javascript:alert('x')")


def test_wrap_plain_text_as_html_escapes_input():
    html = wrap_plain_text_as_html("<b>Hello</b>")
    assert "&lt;b&gt;Hello&lt;/b&gt;" in html

