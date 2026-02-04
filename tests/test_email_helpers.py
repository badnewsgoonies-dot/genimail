import hashlib
import os

from genimail.constants import DEFAULT_CLIENT_ID
from genimail.domain.helpers import (
    build_reply_recipients,
    domain_to_company,
    format_date,
    format_size,
    strip_html,
    token_cache_path_for_client_id,
)
from genimail.paths import CONFIG_DIR, TOKEN_CACHE_FILE


def test_token_cache_path_default_client():
    assert token_cache_path_for_client_id(DEFAULT_CLIENT_ID) == TOKEN_CACHE_FILE
    assert token_cache_path_for_client_id("") == TOKEN_CACHE_FILE
    assert token_cache_path_for_client_id(None) == TOKEN_CACHE_FILE


def test_token_cache_path_custom_client_is_stable():
    client_id = "my-custom-client-id"
    digest = hashlib.sha1(client_id.encode("utf-8")).hexdigest()[:12]
    expected = os.path.join(CONFIG_DIR, f"token_cache_{digest}.json")

    assert token_cache_path_for_client_id(client_id) == expected
    assert token_cache_path_for_client_id(f"  {client_id}  ") == expected


def test_strip_html_removes_tags_and_formats_text():
    raw = """
    <html>
      <head><style>p { color: red; }</style></head>
      <body>
        <script>alert('x')</script>
        <p>Hello&nbsp;World</p>
        <img alt="Invoice" src="x.png" />
        <a href="https://example.com">Click</a>
        <ul><li>Item 1</li></ul>
      </body>
    </html>
    """
    plain = strip_html(raw)

    assert "alert(" not in plain
    assert "Hello World" in plain
    assert "[Image: Invoice]" in plain
    assert "Click [https://example.com]" in plain
    assert "• Item 1" in plain


def test_strip_html_handles_invisible_and_empty_input():
    assert strip_html(None) == ""
    assert strip_html("") == ""
    assert strip_html("Hello\u200b\u200cWorld") == "HelloWorld"


def test_domain_to_company_formats_common_cases():
    assert domain_to_company(None) == "Other"
    assert domain_to_company("acme-corp.com") == "Acme Corp"
    assert domain_to_company("hello_world.io") == "Hello World"
    assert domain_to_company("gmail.com") == "gmail.com"


def test_format_date_handles_valid_and_invalid_inputs():
    assert format_date("2000-01-02T00:00:00Z") == "Jan 02, 2000"
    assert format_date("not-a-date") == "not-a-date"
    assert format_date("") == ""


def test_format_size_thresholds():
    assert format_size(None) == ""
    assert format_size(0) == ""
    assert format_size(512) == "512 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"


def test_build_reply_recipients_reply_mode():
    message = {
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "toRecipients": [{"emailAddress": {"address": "me@example.com"}}],
        "ccRecipients": [{"emailAddress": {"address": "cc@example.com"}}],
    }
    to_list, cc_list = build_reply_recipients(
        message,
        current_user_email="me@example.com",
        include_all=False,
    )
    assert to_list == ["sender@example.com"]
    assert cc_list == []


def test_build_reply_recipients_reply_all_mode_deduplicates():
    message = {
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "toRecipients": [
            {"emailAddress": {"address": "me@example.com"}},
            {"emailAddress": {"address": "other@example.com"}},
            {"emailAddress": {"address": "SENDER@example.com"}},
        ],
        "ccRecipients": [
            {"emailAddress": {"address": "copy@example.com"}},
            {"emailAddress": {"address": "other@example.com"}},
            {"emailAddress": {"address": "ME@example.com"}},
        ],
    }
    to_list, cc_list = build_reply_recipients(
        message,
        current_user_email="me@example.com",
        include_all=True,
    )
    assert to_list == ["sender@example.com", "other@example.com"]
    assert cc_list == ["copy@example.com"]
