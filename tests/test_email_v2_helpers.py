import hashlib
import os
import time

from genimail.constants import DEFAULT_CLIENT_ID
from genimail.domain.helpers import token_cache_path_for_client_id
from genimail.domain.quotes import (
    build_quote_context,
    create_quote_doc,
    latest_doc_file,
    render_quote_template_text,
)
from genimail.paths import CONFIG_DIR, TOKEN_CACHE_FILE


def test_token_cache_path_for_default_and_custom_client():
    assert token_cache_path_for_client_id(DEFAULT_CLIENT_ID) == TOKEN_CACHE_FILE
    assert token_cache_path_for_client_id(None) == TOKEN_CACHE_FILE
    custom = "client-xyz"
    digest = hashlib.sha1(custom.encode("utf-8")).hexdigest()[:12]
    expected = os.path.join(CONFIG_DIR, f"token_cache_{digest}.json")
    assert token_cache_path_for_client_id(custom) == expected
    assert token_cache_path_for_client_id(f"  {custom}  ") == expected


def test_render_quote_template_text_replaces_placeholders():
    template = "Quote {{QUOTE_ID}} for {{CLIENT_NAME}} on {{DATE}}"
    context = {
        "quote_id": "Q123",
        "client_name": "Jane",
        "date": "2026-02-04",
    }
    rendered = render_quote_template_text(template, context)
    assert rendered == "Quote Q123 for Jane on 2026-02-04"


def test_create_quote_doc_creates_default_template_and_output(tmp_path):
    template_path = tmp_path / "missing_template.doc"
    output_dir = tmp_path / "quotes"
    context = {
        "quote_id": "Q1",
        "date": "2026-02-04",
        "client_name": "Client A",
        "client_email": "client@example.com",
        "project_name": "Project",
        "email_subject": "Subject",
    }

    out_path = create_quote_doc(str(template_path), str(output_dir), context)

    assert template_path.exists()
    assert os.path.exists(out_path)
    assert out_path.lower().endswith(".doc")
    content = (output_dir / os.path.basename(out_path)).read_text(encoding="utf-8")
    assert "Client A" in content
    assert "Q1" in content


def test_latest_doc_file_returns_newest_doc(tmp_path):
    older = tmp_path / "old.doc"
    newer = tmp_path / "new.doc"
    older.write_text("old", encoding="utf-8")
    time.sleep(0.01)
    newer.write_text("new", encoding="utf-8")
    assert latest_doc_file(str(tmp_path)) == str(newer)
    assert latest_doc_file(str(tmp_path / "none")) is None


def test_build_quote_context_uses_subject_and_defaults():
    context = build_quote_context(reply_msg=None, to_value="", subject_value="Lobby Paint")
    assert context["project_name"] == "Lobby Paint"
    assert context["email_subject"] == "Lobby Paint"
    assert context["client_name"]


def test_create_quote_doc_keeps_docx_extension_for_zip_templates(tmp_path):
    template_path = tmp_path / "quote_template.docx"
    template_path.write_bytes(b"PK\x03\x04dummy")
    output_dir = tmp_path / "quotes"
    context = {
        "quote_id": "Q2",
        "date": "2026-02-04",
        "client_name": "Client B",
        "client_email": "clientb@example.com",
        "project_name": "Project B",
        "email_subject": "Subject B",
    }

    out_path = create_quote_doc(str(template_path), str(output_dir), context)
    assert out_path.lower().endswith(".docx")
