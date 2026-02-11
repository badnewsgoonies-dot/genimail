import sqlite3
import time

from genimail.infra.cache_store import EmailCache


def test_schema_version_and_recipient_table_present(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))

    row = cache.conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert row["version"] == EmailCache.SCHEMA_VERSION

    table_row = cache.conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'message_recipients'"
    ).fetchone()
    assert table_row is not None
    fk_enabled = cache.conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_enabled == 1


def test_save_and_load_messages_include_recipients_and_domain_search(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [
            {
                "id": "m1",
                "subject": "Invoice",
                "from": {"emailAddress": {"name": "Me", "address": "me@mycompany.com"}},
                "toRecipients": [
                    {"emailAddress": {"name": "Acme Billing", "address": "Billing@Acme.com"}},
                ],
                "ccRecipients": [
                    {"emailAddress": {"name": "Acme Support", "address": "support@acme.com"}},
                ],
                "receivedDateTime": "2026-01-01T00:00:00Z",
                "isRead": False,
                "hasAttachments": False,
                "bodyPreview": "Payment due",
                "importance": "normal",
            }
        ],
        folder_id="sentitems",
    )

    rows = cache.get_messages("sentitems")
    assert len(rows) == 1
    msg = rows[0]
    assert [item["emailAddress"]["address"] for item in msg["toRecipients"]] == ["billing@acme.com"]
    assert [item["emailAddress"]["address"] for item in msg["ccRecipients"]] == ["support@acme.com"]

    from_sender = cache.search_by_domain("mycompany.com")
    assert [item["id"] for item in from_sender] == ["m1"]

    from_recipients = cache.search_by_domain("acme.com")
    assert [item["id"] for item in from_recipients] == ["m1"]


def test_delete_messages_removes_recipient_rows(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [
            {
                "id": "m1",
                "subject": "Hello",
                "from": {"emailAddress": {"name": "Sender", "address": "sender@example.com"}},
                "toRecipients": [{"emailAddress": {"name": "To", "address": "to@example.com"}}],
                "ccRecipients": [],
                "receivedDateTime": "2026-01-01T00:00:00Z",
                "isRead": True,
                "hasAttachments": False,
                "bodyPreview": "",
                "importance": "normal",
            }
        ],
        folder_id="inbox",
    )

    count_before = cache.conn.execute("SELECT COUNT(*) AS count FROM message_recipients").fetchone()["count"]
    assert count_before == 1

    cache.delete_messages(["m1"])
    count_after = cache.conn.execute("SELECT COUNT(*) AS count FROM message_recipients").fetchone()["count"]
    assert count_after == 0


def test_search_company_messages_supports_email_domain_and_text(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [
            {
                "id": "a",
                "subject": "Invoice reminder",
                "from": {"emailAddress": {"name": "Sender A", "address": "sender@example.com"}},
                "toRecipients": [{"emailAddress": {"name": "Acme AP", "address": "billing@acme.com"}}],
                "ccRecipients": [],
                "receivedDateTime": "2026-01-02T00:00:00Z",
                "isRead": False,
                "hasAttachments": False,
                "bodyPreview": "invoice",
                "importance": "normal",
            },
            {
                "id": "b",
                "subject": "Status",
                "from": {"emailAddress": {"name": "Acme Bot", "address": "bot@acme.com"}},
                "toRecipients": [],
                "ccRecipients": [],
                "receivedDateTime": "2026-01-01T00:00:00Z",
                "isRead": True,
                "hasAttachments": False,
                "bodyPreview": "",
                "importance": "normal",
            },
        ],
        folder_id="inbox",
    )

    by_email = cache.search_company_messages("billing@acme.com")
    assert [msg["id"] for msg in by_email] == ["a"]

    by_domain = cache.search_company_messages("acme.com")
    assert [msg["id"] for msg in by_domain] == ["a", "b"]

    by_text = cache.search_company_messages("acme ap")
    assert [msg["id"] for msg in by_text] == ["a"]


def test_search_company_messages_with_search_text_uses_body_content(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [
            {
                "id": "x1",
                "subject": "Status Update",
                "from": {"emailAddress": {"name": "Acme Ops", "address": "ops@acme.com"}},
                "toRecipients": [],
                "ccRecipients": [],
                "receivedDateTime": "2026-01-03T00:00:00Z",
                "isRead": False,
                "hasAttachments": False,
                "bodyPreview": "summary",
                "importance": "normal",
            }
        ],
        folder_id="inbox",
    )
    cache.save_message_body("x1", "text", "Quarterly revenue packet attached")

    results = cache.search_company_messages("acme.com", search_text="quarterly revenue")
    assert [msg["id"] for msg in results] == ["x1"]


def test_search_company_messages_search_text_falls_back_without_fts(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_messages(
        [
            {
                "id": "y1",
                "subject": "Invoice Ready",
                "from": {"emailAddress": {"name": "Acme Billing", "address": "billing@acme.com"}},
                "toRecipients": [],
                "ccRecipients": [],
                "receivedDateTime": "2026-01-04T00:00:00Z",
                "isRead": False,
                "hasAttachments": False,
                "bodyPreview": "invoice details",
                "importance": "normal",
            }
        ],
        folder_id="inbox",
    )

    cache._fts5_supported_cache = False
    results = cache.search_company_messages("acme.com", search_text="invoice")
    assert [msg["id"] for msg in results] == ["y1"]


def test_search_company_messages_default_does_not_truncate_large_result_sets(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    messages = []
    for idx in range(520):
        messages.append(
            {
                "id": f"bulk-{idx}",
                "subject": f"Bulk {idx}",
                "from": {"emailAddress": {"name": "Acme Bot", "address": f"bot{idx}@acme.com"}},
                "toRecipients": [],
                "ccRecipients": [],
                "receivedDateTime": f"2026-01-05T00:{idx % 60:02d}:00Z",
                "isRead": True,
                "hasAttachments": False,
                "bodyPreview": "bulk import",
                "importance": "normal",
            }
        )
    cache.save_messages(messages, folder_id="inbox")

    results = cache.search_company_messages("acme.com")
    assert len(results) == 520


def test_legacy_schema_v1_migrates_to_latest_without_data_loss(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version(version) VALUES (1);

        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            folder_id TEXT NOT NULL,
            subject TEXT,
            sender_name TEXT,
            sender_address TEXT,
            received_datetime TEXT,
            is_read INTEGER DEFAULT 0,
            has_attachments INTEGER DEFAULT 0,
            body_preview TEXT,
            importance TEXT,
            company_label TEXT,
            cached_at INTEGER NOT NULL
        );

        CREATE TABLE message_bodies (
            id TEXT PRIMARY KEY,
            content_type TEXT,
            content TEXT,
            cached_at INTEGER NOT NULL
        );

        CREATE TABLE attachments (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            name TEXT,
            size INTEGER,
            content_type TEXT,
            cached_at INTEGER NOT NULL
        );

        CREATE TABLE sync_state (
            folder_id TEXT PRIMARY KEY,
            delta_link TEXT,
            last_sync INTEGER
        );

        """
    )
    conn.execute(
        """INSERT INTO messages
           (id, folder_id, subject, sender_name, sender_address, received_datetime,
            is_read, has_attachments, body_preview, importance, company_label, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "legacy-1",
            "inbox",
            "Legacy",
            "Legacy Sender",
            "legacy@example.com",
            "2026-01-01T00:00:00Z",
            0,
            0,
            "legacy preview",
            "normal",
            None,
            int(time.time()),
        ),
    )
    conn.commit()
    conn.close()

    cache = EmailCache(db_path=str(db_path))

    version_row = cache.conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert version_row["version"] == EmailCache.SCHEMA_VERSION

    migrated = cache.get_messages("inbox")
    assert [msg["id"] for msg in migrated] == ["legacy-1"]


def test_clear_single_delta_link_only_affects_target_folder(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    cache.save_delta_link("inbox", "delta-inbox")
    cache.save_delta_link("sentitems", "delta-sent")

    cache.clear_delta_link("inbox")

    assert cache.get_delta_link("inbox") is None
    assert cache.get_delta_link("sentitems") == "delta-sent"


def test_close_resets_connection_and_allows_reopen(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    _ = cache.conn

    cache.close()

    assert getattr(cache._local, "conn", None) is None
    assert cache.get_message_count() == 0


def test_delete_messages_handles_large_batches_with_chunking(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    messages = []
    for idx in range(1105):
        messages.append(
            {
                "id": f"chunk-{idx}",
                "subject": f"Chunk {idx}",
                "from": {"emailAddress": {"name": "Sender", "address": "sender@example.com"}},
                "toRecipients": [],
                "ccRecipients": [],
                "receivedDateTime": f"2026-01-01T00:{idx % 60:02d}:00Z",
                "isRead": False,
                "hasAttachments": False,
                "bodyPreview": "bulk",
                "importance": "normal",
            }
        )
    cache.save_messages(messages, folder_id="inbox")

    all_ids = [msg["id"] for msg in messages]
    cache.delete_messages(all_ids)

    assert cache.get_message_count("inbox") == 0
