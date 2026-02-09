from genimail.infra.cache_store import EmailCache


def _make_msg(msg_id, subject="Test", sender_name="Sender", sender_address="sender@example.com",
              body_preview="preview", folder_id="inbox", to=None, cc=None):
    return {
        "id": msg_id,
        "subject": subject,
        "from": {"emailAddress": {"name": sender_name, "address": sender_address}},
        "toRecipients": to or [],
        "ccRecipients": cc or [],
        "receivedDateTime": "2026-01-01T00:00:00Z",
        "isRead": False,
        "hasAttachments": False,
        "bodyPreview": body_preview,
        "importance": "normal",
    }


def test_search_messages_finds_by_subject(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", subject="Invoice reminder")], folder_id="inbox")
    results = cache.search_messages("invoice")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_finds_by_body_preview(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", body_preview="payment due soon")], folder_id="inbox")
    results = cache.search_messages("payment due")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_finds_by_sender_name(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", sender_name="Alice Johnson")], folder_id="inbox")
    results = cache.search_messages("alice")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_finds_by_sender_address(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", sender_address="alice@widgets.com")], folder_id="inbox")
    results = cache.search_messages("widgets.com")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_finds_by_body_content(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", subject="Hello")], folder_id="inbox")
    cache.save_message_body("m1", "text", "Quarterly revenue report attached")
    results = cache.search_messages("quarterly revenue")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_finds_by_recipient(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [_make_msg("m1", to=[{"emailAddress": {"name": "Bob", "address": "bob@acme.com"}}])],
        folder_id="inbox",
    )
    results = cache.search_messages("bob@acme")
    assert [msg["id"] for msg in results] == ["m1"]


def test_search_messages_respects_folder_id(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", subject="Invoice")], folder_id="inbox")
    cache.save_messages([_make_msg("m2", subject="Invoice copy")], folder_id="sentitems")
    results_inbox = cache.search_messages("invoice", folder_id="inbox")
    assert [msg["id"] for msg in results_inbox] == ["m1"]
    results_all = cache.search_messages("invoice")
    assert sorted(msg["id"] for msg in results_all) == ["m1", "m2"]


def test_search_messages_returns_empty_for_no_match(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", subject="Hello world")], folder_id="inbox")
    results = cache.search_messages("xyznonexistent")
    assert results == []


def test_search_messages_respects_limit(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    for i in range(10):
        cache.save_messages([_make_msg(f"m{i}", subject="Report")], folder_id="inbox")
    results = cache.search_messages("report", limit=3)
    assert len(results) == 3


def test_search_messages_empty_text_returns_empty(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1")], folder_id="inbox")
    assert cache.search_messages("") == []
    assert cache.search_messages("   ") == []


def test_search_messages_like_fallback_when_fts_disabled(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages([_make_msg("m1", subject="Invoice reminder")], folder_id="inbox")
    cache._fts5_supported_cache = False
    results = cache.search_messages("invoice")
    assert [msg["id"] for msg in results] == ["m1"]
