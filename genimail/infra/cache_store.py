import os
import sqlite3
import threading
import time

from genimail.paths import CACHE_DB_FILE


class EmailCache:
    """SQLite-based persistent cache for emails with thread-safe connections."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path=None):
        self.db_path = db_path or CACHE_DB_FILE
        self._local = threading.local()
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # Skip for :memory: or relative paths without directory
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()

    @property
    def conn(self):
        """Thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_schema(self):
        """Create database tables if they don't exist."""
        conn = self.conn
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS messages (
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

            CREATE TABLE IF NOT EXISTS message_bodies (
                id TEXT PRIMARY KEY,
                content_type TEXT,
                content TEXT,
                cached_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                name TEXT,
                size INTEGER,
                content_type TEXT,
                cached_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                folder_id TEXT PRIMARY KEY,
                delta_link TEXT,
                last_sync INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_messages_folder ON messages(folder_id, received_datetime DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_cached ON messages(cached_at);
            CREATE INDEX IF NOT EXISTS idx_messages_company ON messages(company_label);
            CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_address);
            CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);
        """
        )
        conn.commit()

    def get_messages(self, folder_id, limit=100, offset=0):
        """Get cached messages for a folder."""
        cur = self.conn.execute(
            """SELECT id, folder_id, subject, sender_name, sender_address,
                      received_datetime, is_read, has_attachments, body_preview,
                      importance, company_label
               FROM messages
               WHERE folder_id = ?
               ORDER BY received_datetime DESC
               LIMIT ? OFFSET ?""",
            (folder_id, limit, offset),
        )
        rows = cur.fetchall()
        return [self._row_to_message(row) for row in rows]

    def _row_to_message(self, row):
        """Convert a database row to a message dict matching Graph API format."""
        return {
            "id": row["id"],
            "subject": row["subject"],
            "from": {
                "emailAddress": {
                    "name": row["sender_name"],
                    "address": row["sender_address"],
                }
            },
            "receivedDateTime": row["received_datetime"],
            "isRead": bool(row["is_read"]),
            "hasAttachments": bool(row["has_attachments"]),
            "bodyPreview": row["body_preview"],
            "importance": row["importance"],
            "_companyLabel": row["company_label"],
            "_fromCache": True,
        }

    def save_messages(self, messages, folder_id):
        """Save messages to cache (batch insert/update)."""
        now = int(time.time())
        conn = self.conn
        for msg in messages:
            sender = msg.get("from", {}).get("emailAddress", {})
            conn.execute(
                """INSERT OR REPLACE INTO messages
                   (id, folder_id, subject, sender_name, sender_address,
                    received_datetime, is_read, has_attachments, body_preview,
                    importance, company_label, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           COALESCE((SELECT company_label FROM messages WHERE id = ?), NULL),
                           ?)""",
                (
                    msg["id"],
                    folder_id,
                    msg.get("subject"),
                    sender.get("name"),
                    sender.get("address"),
                    msg.get("receivedDateTime"),
                    1 if msg.get("isRead") else 0,
                    1 if msg.get("hasAttachments") else 0,
                    msg.get("bodyPreview"),
                    msg.get("importance"),
                    msg["id"],
                    now,
                ),
            )
        conn.commit()

    def get_message_body(self, msg_id):
        """Get cached full message body."""
        cur = self.conn.execute("SELECT content_type, content FROM message_bodies WHERE id = ?", (msg_id,))
        row = cur.fetchone()
        if row:
            return {"contentType": row["content_type"], "content": row["content"]}
        return None

    def save_message_body(self, msg_id, content_type, content):
        """Save full message body to cache."""
        self.conn.execute(
            """INSERT OR REPLACE INTO message_bodies (id, content_type, content, cached_at)
               VALUES (?, ?, ?, ?)""",
            (msg_id, content_type, content, int(time.time())),
        )
        self.conn.commit()

    def get_attachments(self, msg_id):
        """Get cached attachment metadata for a message."""
        cur = self.conn.execute(
            "SELECT id, name, size, content_type FROM attachments WHERE message_id = ?",
            (msg_id,),
        )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "size": row["size"],
                "contentType": row["content_type"],
                "@odata.type": "#microsoft.graph.fileAttachment",
            }
            for row in cur.fetchall()
        ]

    def save_attachments(self, msg_id, attachments):
        """Save attachment metadata to cache."""
        now = int(time.time())
        conn = self.conn
        for att in attachments:
            if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
                conn.execute(
                    """INSERT OR REPLACE INTO attachments
                       (id, message_id, name, size, content_type, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        att["id"],
                        msg_id,
                        att.get("name"),
                        att.get("size"),
                        att.get("contentType"),
                        now,
                    ),
                )
        conn.commit()

    def update_read_status(self, msg_id, is_read):
        """Update read status in cache."""
        self.conn.execute("UPDATE messages SET is_read = ? WHERE id = ?", (1 if is_read else 0, msg_id))
        self.conn.commit()

    def delete_messages(self, message_ids):
        """Remove deleted messages from cache."""
        if not message_ids:
            return
        placeholders = ",".join("?" * len(message_ids))
        conn = self.conn
        ids_tuple = tuple(message_ids)
        conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids_tuple)
        conn.execute(f"DELETE FROM message_bodies WHERE id IN ({placeholders})", ids_tuple)
        conn.execute(f"DELETE FROM attachments WHERE message_id IN ({placeholders})", ids_tuple)
        conn.commit()

    def prune_old(self, days=30):
        """Delete cache entries older than N days."""
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        conn = self.conn
        conn.execute("DELETE FROM messages WHERE cached_at < ?", (cutoff,))
        conn.execute("DELETE FROM message_bodies WHERE cached_at < ?", (cutoff,))
        conn.execute("DELETE FROM attachments WHERE cached_at < ?", (cutoff,))
        conn.commit()

    def clear(self):
        """Reset entire cache."""
        conn = self.conn
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM message_bodies")
        conn.execute("DELETE FROM attachments")
        conn.execute("DELETE FROM sync_state")
        conn.commit()

    def search_by_domain(self, domain):
        """Find all emails from a specific domain."""
        cur = self.conn.execute(
            """SELECT id, folder_id, subject, sender_name, sender_address,
                      received_datetime, is_read, has_attachments, body_preview,
                      importance, company_label
               FROM messages
               WHERE sender_address LIKE ?
               ORDER BY received_datetime DESC""",
            (f"%@{domain}",),
        )
        return [self._row_to_message(row) for row in cur.fetchall()]

    def search_by_company_label(self, label):
        """Find all emails with a specific company label."""
        cur = self.conn.execute(
            """SELECT id, folder_id, subject, sender_name, sender_address,
                      received_datetime, is_read, has_attachments, body_preview,
                      importance, company_label
               FROM messages
               WHERE company_label = ?
               ORDER BY received_datetime DESC""",
            (label,),
        )
        return [self._row_to_message(row) for row in cur.fetchall()]

    def label_domain(self, domain, label):
        """Bulk-label all emails from a domain."""
        cur = self.conn.execute(
            "UPDATE messages SET company_label = ? WHERE sender_address LIKE ?",
            (label, f"%@{domain}"),
        )
        self.conn.commit()
        return cur.rowcount

    def get_all_domains(self):
        """Get all unique sender domains with counts."""
        cur = self.conn.execute(
            """SELECT
                 LOWER(SUBSTR(sender_address, INSTR(sender_address, '@') + 1)) as domain,
                 COUNT(*) as count,
                 company_label,
                 MAX(received_datetime) as last_email
               FROM messages
               WHERE sender_address LIKE '%@%'
               GROUP BY domain
               ORDER BY count DESC"""
        )
        return [dict(row) for row in cur.fetchall()]

    def get_unlabeled_domains(self):
        """Get domains that haven't been labeled yet."""
        cur = self.conn.execute(
            """SELECT
                 LOWER(SUBSTR(sender_address, INSTR(sender_address, '@') + 1)) as domain,
                 COUNT(*) as count
               FROM messages
               WHERE sender_address LIKE '%@%'
                 AND (company_label IS NULL OR company_label = '')
               GROUP BY domain
               ORDER BY count DESC"""
        )
        return [dict(row) for row in cur.fetchall()]

    def get_message_count(self, folder_id=None):
        """Get total cached message count."""
        if folder_id:
            cur = self.conn.execute("SELECT COUNT(*) as count FROM messages WHERE folder_id = ?", (folder_id,))
        else:
            cur = self.conn.execute("SELECT COUNT(*) as count FROM messages")
        return cur.fetchone()["count"]

    def get_delta_link(self, folder_id):
        """Get stored delta link for a folder."""
        cur = self.conn.execute("SELECT delta_link FROM sync_state WHERE folder_id = ?", (folder_id,))
        row = cur.fetchone()
        return row["delta_link"] if row else None

    def save_delta_link(self, folder_id, delta_link):
        """Store delta link for a folder."""
        self.conn.execute(
            """INSERT OR REPLACE INTO sync_state (folder_id, delta_link, last_sync)
               VALUES (?, ?, ?)""",
            (folder_id, delta_link, int(time.time())),
        )
        self.conn.commit()

