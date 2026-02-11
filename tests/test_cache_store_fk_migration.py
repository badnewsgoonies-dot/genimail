import sqlite3
import time

from genimail.infra.cache_store import EmailCache


def _create_legacy_v3_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version(version) VALUES (3);

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

        CREATE TABLE message_recipients (
            message_id TEXT NOT NULL,
            role TEXT NOT NULL,
            recipient_name TEXT,
            recipient_address TEXT NOT NULL,
            cached_at INTEGER NOT NULL,
            PRIMARY KEY (message_id, role, recipient_address)
        );

        CREATE TABLE sync_state (
            folder_id TEXT PRIMARY KEY,
            delta_link TEXT,
            last_sync INTEGER
        );
        """
    )
    now = int(time.time())
    conn.execute(
        """INSERT INTO messages
           (id, folder_id, subject, sender_name, sender_address, received_datetime,
            is_read, has_attachments, body_preview, importance, company_label, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "legacy-1",
            "inbox",
            "Legacy Subject",
            "Legacy Sender",
            "legacy@example.com",
            "2026-01-01T00:00:00Z",
            0,
            1,
            "legacy preview",
            "normal",
            None,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO message_bodies (id, content_type, content, cached_at) VALUES (?, ?, ?, ?)",
        ("legacy-1", "text", "legacy body", now),
    )
    conn.execute(
        "INSERT INTO attachments (id, message_id, name, size, content_type, cached_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("att-1", "legacy-1", "legacy.txt", 123, "text/plain", now),
    )
    conn.execute(
        """INSERT INTO message_recipients
           (message_id, role, recipient_name, recipient_address, cached_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("legacy-1", "to", "Recipient", "recipient@example.com", now),
    )
    conn.commit()
    conn.close()


def _fk_targets(conn, table_name):
    rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return [row["table"] for row in rows]


def test_v4_fk_migration_retrofits_legacy_tables_and_preserves_data(tmp_path):
    db_path = tmp_path / "legacy_v3.db"
    _create_legacy_v3_db(db_path)

    cache = EmailCache(db_path=str(db_path))

    version_row = cache.conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert version_row["version"] == EmailCache.SCHEMA_VERSION

    assert "messages" in _fk_targets(cache.conn, "message_bodies")
    assert "messages" in _fk_targets(cache.conn, "attachments")
    assert "messages" in _fk_targets(cache.conn, "message_recipients")

    rows = cache.get_messages("inbox")
    assert [row["id"] for row in rows] == ["legacy-1"]
    assert cache.get_message_body("legacy-1")["content"] == "legacy body"
    assert [att["id"] for att in cache.get_attachments("legacy-1")] == ["att-1"]


def test_v4_fk_migration_enables_on_delete_cascade(tmp_path):
    db_path = tmp_path / "legacy_v3_cascade.db"
    _create_legacy_v3_db(db_path)
    cache = EmailCache(db_path=str(db_path))

    cache.conn.execute("DELETE FROM messages WHERE id = ?", ("legacy-1",))
    cache.conn.commit()

    assert cache.get_message_body("legacy-1") is None
    assert cache.get_attachments("legacy-1") == []
    recipient_count = cache.conn.execute(
        "SELECT COUNT(*) AS count FROM message_recipients WHERE message_id = ?",
        ("legacy-1",),
    ).fetchone()["count"]
    assert recipient_count == 0
