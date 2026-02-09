import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger(__name__)

from genimail.constants import SQL_PARAM_CHUNK_SIZE
from genimail.paths import CACHE_DB_FILE


class EmailCache:
    """SQLite-based persistent cache for emails with thread-safe connections."""

    SCHEMA_VERSION = 3

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
        current_version = self._current_schema_version(conn)
        if current_version < 1:
            self._migrate_to_v1(conn)
        if current_version < 2:
            self._migrate_to_v2(conn)
        if current_version < 3:
            self._migrate_to_v3(conn)
        self._set_schema_version(conn, self.SCHEMA_VERSION)
        conn.commit()

    @staticmethod
    def _current_schema_version(conn):
        cur = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cur.fetchone()
        return int(row["version"]) if row else 0

    @staticmethod
    def _set_schema_version(conn, version):
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (int(version),))

    @staticmethod
    def _migrate_to_v1(conn):
        # Baseline schema is created in _init_schema via CREATE TABLE IF NOT EXISTS.
        _ = conn

    @staticmethod
    def _migrate_to_v2(conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS message_recipients (
                message_id TEXT NOT NULL,
                role TEXT NOT NULL,
                recipient_name TEXT,
                recipient_address TEXT NOT NULL,
                cached_at INTEGER NOT NULL,
                PRIMARY KEY (message_id, role, recipient_address)
            );
            CREATE INDEX IF NOT EXISTS idx_message_recipients_message ON message_recipients(message_id);
            CREATE INDEX IF NOT EXISTS idx_message_recipients_address ON message_recipients(recipient_address);
            """
        )

    def _fts5_supported(self, conn=None):
        if hasattr(self, "_fts5_supported_cache"):
            return bool(self._fts5_supported_cache)
        active_conn = conn or self.conn
        try:
            active_conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(content)")
            active_conn.execute("DROP TABLE IF EXISTS __fts5_probe")
            self._fts5_supported_cache = True
        except sqlite3.OperationalError:
            self._fts5_supported_cache = False
        return bool(self._fts5_supported_cache)

    @staticmethod
    def _fts_table_exists(conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'message_search_fts'"
        ).fetchone()
        return row is not None

    def _is_fts_enabled(self, conn=None):
        active_conn = conn or self.conn
        return self._fts5_supported(active_conn) and self._fts_table_exists(active_conn)

    def _migrate_to_v3(self, conn):
        if not self._fts5_supported(conn):
            return
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS message_search_fts USING fts5(message_id UNINDEXED, searchable_text)"
        )
        self._rebuild_search_index(conn)

    @staticmethod
    def _fts_query_from_text(text):
        tokens = [token.strip() for token in (text or "").split() if token.strip()]
        if not tokens:
            return ""
        escaped_tokens = []
        for token in tokens:
            raw = token.replace('"', '""')
            if raw.endswith("*"):
                base = raw[:-1].replace("*", "")
                if base:
                    escaped_tokens.append(f'"{base}"*')
            else:
                escaped_tokens.append(f'"{raw}"')
        return " AND ".join(escaped_tokens)

    @staticmethod
    def _chunked(values, size=SQL_PARAM_CHUNK_SIZE):
        for idx in range(0, len(values), size):
            yield values[idx : idx + size]

    @staticmethod
    def _unique_message_ids(message_ids):
        ordered = []
        seen = set()
        for value in message_ids or []:
            msg_id = (value or "").strip()
            if not msg_id or msg_id in seen:
                continue
            seen.add(msg_id)
            ordered.append(msg_id)
        return ordered

    _BASE_MESSAGE_SELECT = (
        "m.id, m.folder_id, m.subject, m.sender_name, m.sender_address, "
        "m.received_datetime, m.is_read, m.has_attachments, m.body_preview, "
        "m.importance, m.company_label"
    )

    def _build_company_predicate(self, normalized):
        if "@" in normalized and " " not in normalized:
            return (
                "("
                "LOWER(COALESCE(m.sender_address, '')) = ? "
                "OR EXISTS ("
                "SELECT 1 FROM message_recipients r "
                "WHERE r.message_id = m.id AND LOWER(COALESCE(r.recipient_address, '')) = ?"
                ")"
                ")",
                [normalized, normalized],
            )

        if "." in normalized and "@" not in normalized and " " not in normalized:
            domain_like = f"%@{normalized}"
            return (
                "("
                "LOWER(COALESCE(m.sender_address, '')) LIKE ? "
                "OR EXISTS ("
                "SELECT 1 FROM message_recipients r "
                "WHERE r.message_id = m.id AND LOWER(COALESCE(r.recipient_address, '')) LIKE ?"
                ")"
                ")",
                [domain_like, domain_like],
            )

        like_value = f"%{normalized}%"
        return (
            "("
            "LOWER(COALESCE(m.sender_address, '')) LIKE ? "
            "OR LOWER(COALESCE(m.sender_name, '')) LIKE ? "
            "OR EXISTS ("
            "SELECT 1 FROM message_recipients r "
            "WHERE r.message_id = m.id AND ("
            "LOWER(COALESCE(r.recipient_address, '')) LIKE ? "
            "OR LOWER(COALESCE(r.recipient_name, '')) LIKE ?"
            ")"
            ")"
            ")",
            [like_value, like_value, like_value, like_value],
        )

    def _search_company_messages_like(self, normalized, search_text="", limit=None):
        company_clause, company_params = self._build_company_predicate(normalized)
        params = list(company_params)
        search_clause = ""
        if search_text:
            like_value = f"%{search_text}%"
            search_clause = (
                " AND ("
                "LOWER(COALESCE(m.subject, '')) LIKE ? "
                "OR LOWER(COALESCE(m.body_preview, '')) LIKE ? "
                "OR LOWER(COALESCE(m.sender_name, '')) LIKE ? "
                "OR LOWER(COALESCE(m.sender_address, '')) LIKE ? "
                "OR EXISTS ("
                "SELECT 1 FROM message_recipients sr "
                "WHERE sr.message_id = m.id AND ("
                "LOWER(COALESCE(sr.recipient_name, '')) LIKE ? "
                "OR LOWER(COALESCE(sr.recipient_address, '')) LIKE ?"
                ")"
                ") "
                "OR EXISTS ("
                "SELECT 1 FROM message_bodies mb "
                "WHERE mb.id = m.id AND LOWER(COALESCE(mb.content, '')) LIKE ?"
                ")"
                ")"
            )
            params.extend([like_value, like_value, like_value, like_value, like_value, like_value, like_value])
        limit_clause = ""
        if limit is not None:
            limit_clause = "\n               LIMIT ?"
            params.append(int(limit))
        cur = self.conn.execute(
            f"""SELECT {self._BASE_MESSAGE_SELECT}
               FROM messages m
               WHERE {company_clause}{search_clause}
               ORDER BY m.received_datetime DESC{limit_clause}""",
            tuple(params),
        )
        return self._rows_to_messages(cur.fetchall())

    def _search_company_messages_fts(self, normalized, search_text, limit=None):
        company_clause, company_params = self._build_company_predicate(normalized)
        fts_query = self._fts_query_from_text(search_text)
        if not fts_query:
            return self._search_company_messages_like(normalized, search_text=search_text, limit=limit)
        params = [*company_params, fts_query]
        limit_clause = ""
        if limit is not None:
            limit_clause = "\n               LIMIT ?"
            params.append(int(limit))
        cur = self.conn.execute(
            f"""SELECT {self._BASE_MESSAGE_SELECT}
               FROM messages m
               JOIN message_search_fts f ON f.message_id = m.id
               WHERE {company_clause}
                 AND message_search_fts MATCH ?
               ORDER BY bm25(message_search_fts), m.received_datetime DESC{limit_clause}""",
            tuple(params),
        )
        return self._rows_to_messages(cur.fetchall())

    def _build_searchable_texts(self, conn, message_ids):
        documents = {}
        for chunk in self._chunked(message_ids):
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"""SELECT m.id, m.subject, m.sender_name, m.sender_address, m.body_preview, mb.content AS body_content
                    FROM messages m
                    LEFT JOIN message_bodies mb ON mb.id = m.id
                    WHERE m.id IN ({placeholders})""",
                tuple(chunk),
            ).fetchall()
            for row in rows:
                documents[row["id"]] = [
                    row["subject"] or "",
                    row["sender_name"] or "",
                    row["sender_address"] or "",
                    row["body_preview"] or "",
                    row["body_content"] or "",
                ]

            recip_rows = conn.execute(
                f"""SELECT message_id, recipient_name, recipient_address
                    FROM message_recipients
                    WHERE message_id IN ({placeholders})""",
                tuple(chunk),
            ).fetchall()
            for row in recip_rows:
                bucket = documents.get(row["message_id"])
                if bucket is None:
                    continue
                bucket.append(row["recipient_name"] or "")
                bucket.append(row["recipient_address"] or "")

        result = {}
        for msg_id, parts in documents.items():
            text = " ".join(part for part in parts if part).strip()
            if text:
                result[msg_id] = text
        return result

    def _upsert_search_index_for_messages(self, message_ids, conn=None):
        active_conn = conn or self.conn
        if not self._is_fts_enabled(active_conn):
            return
        unique_ids = self._unique_message_ids(message_ids)
        if not unique_ids:
            return

        for chunk in self._chunked(unique_ids):
            placeholders = ",".join("?" for _ in chunk)
            active_conn.execute(f"DELETE FROM message_search_fts WHERE message_id IN ({placeholders})", tuple(chunk))

        documents = self._build_searchable_texts(active_conn, unique_ids)
        rows_to_insert = [(msg_id, documents[msg_id]) for msg_id in unique_ids if msg_id in documents]
        if rows_to_insert:
            active_conn.executemany(
                "INSERT INTO message_search_fts (message_id, searchable_text) VALUES (?, ?)",
                rows_to_insert,
            )

    def _rebuild_search_index(self, conn=None):
        active_conn = conn or self.conn
        if not self._is_fts_enabled(active_conn):
            return
        active_conn.execute("DELETE FROM message_search_fts")
        rows = active_conn.execute("SELECT id FROM messages").fetchall()
        self._upsert_search_index_for_messages([row["id"] for row in rows], conn=active_conn)

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
        return self._rows_to_messages(rows)

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
            "_folder_id": row["folder_id"],
            "toRecipients": [],
            "ccRecipients": [],
        }

    def _rows_to_messages(self, rows):
        """Convert DB rows to Graph-API-shaped dicts, hydrating recipients via extra queries."""
        messages = [self._row_to_message(row) for row in rows]
        recipient_map = self._recipient_map_for_messages([msg["id"] for msg in messages if msg.get("id")])
        for message in messages:
            msg_id = message.get("id")
            recipient_data = recipient_map.get(msg_id, {"toRecipients": [], "ccRecipients": []})
            message["toRecipients"] = list(recipient_data.get("toRecipients") or [])
            message["ccRecipients"] = list(recipient_data.get("ccRecipients") or [])
        return messages

    def _recipient_map_for_messages(self, message_ids):
        unique_ids = self._unique_message_ids(message_ids)
        if not unique_ids:
            return {}
        recipient_map = {}
        for chunk in self._chunked(unique_ids):
            placeholders = ",".join("?" for _ in chunk)
            cur = self.conn.execute(
                f"""SELECT message_id, role, recipient_name, recipient_address
                   FROM message_recipients
                   WHERE message_id IN ({placeholders})
                   ORDER BY message_id, role, recipient_address""",
                tuple(chunk),
            )
            for row in cur.fetchall():
                msg_id = row["message_id"]
                role = (row["role"] or "").strip().lower()
                if role == "to":
                    key = "toRecipients"
                elif role == "cc":
                    key = "ccRecipients"
                else:
                    continue
                bucket = recipient_map.setdefault(msg_id, {"toRecipients": [], "ccRecipients": []})
                bucket[key].append(
                    {
                        "emailAddress": {
                            "name": row["recipient_name"],
                            "address": row["recipient_address"],
                        }
                    }
                )
        return recipient_map

    @staticmethod
    def _extract_recipients(msg):
        recipients = []
        seen = set()
        for role, field in (("to", "toRecipients"), ("cc", "ccRecipients")):
            for entry in msg.get(field) or []:
                email = (entry or {}).get("emailAddress", {})
                address = (email.get("address") or "").strip().lower()
                if not address:
                    continue
                dedupe_key = (role, address)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                recipients.append((role, (email.get("name") or "").strip(), address))
        return recipients

    def save_messages(self, messages, folder_id):
        """Save messages to cache (batch insert/update)."""
        now = int(time.time())
        conn = self.conn
        updated_ids = []
        for msg in messages:
            msg_id = msg["id"]
            updated_ids.append(msg_id)
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
                    msg_id,
                    folder_id,
                    msg.get("subject"),
                    sender.get("name"),
                    sender.get("address"),
                    msg.get("receivedDateTime"),
                    1 if msg.get("isRead") else 0,
                    1 if msg.get("hasAttachments") else 0,
                    msg.get("bodyPreview"),
                    msg.get("importance"),
                    msg_id,
                    now,
                ),
            )
            conn.execute("DELETE FROM message_recipients WHERE message_id = ?", (msg_id,))
            for role, recipient_name, recipient_address in self._extract_recipients(msg):
                conn.execute(
                    """INSERT OR REPLACE INTO message_recipients
                       (message_id, role, recipient_name, recipient_address, cached_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (msg_id, role, recipient_name, recipient_address, now),
                )
        self._upsert_search_index_for_messages(updated_ids, conn=conn)
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
        conn = self.conn
        conn.execute(
            """INSERT OR REPLACE INTO message_bodies (id, content_type, content, cached_at)
               VALUES (?, ?, ?, ?)""",
            (msg_id, content_type, content, int(time.time())),
        )
        self._upsert_search_index_for_messages([msg_id], conn=conn)
        conn.commit()

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
        conn.execute(f"DELETE FROM message_recipients WHERE message_id IN ({placeholders})", ids_tuple)
        if self._is_fts_enabled(conn):
            conn.execute(f"DELETE FROM message_search_fts WHERE message_id IN ({placeholders})", ids_tuple)
        conn.commit()

    def prune_old(self, days=30):
        """Delete cache entries older than N days."""
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        conn = self.conn
        conn.execute("DELETE FROM messages WHERE cached_at < ?", (cutoff,))
        conn.execute("DELETE FROM message_bodies WHERE cached_at < ?", (cutoff,))
        conn.execute("DELETE FROM attachments WHERE cached_at < ?", (cutoff,))
        conn.execute("DELETE FROM message_recipients WHERE message_id NOT IN (SELECT id FROM messages)")
        if self._is_fts_enabled(conn):
            conn.execute("DELETE FROM message_search_fts WHERE message_id NOT IN (SELECT id FROM messages)")
        conn.commit()

    def clear(self):
        """Reset entire cache."""
        conn = self.conn
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM message_bodies")
        conn.execute("DELETE FROM attachments")
        conn.execute("DELETE FROM message_recipients")
        if self._is_fts_enabled(conn):
            conn.execute("DELETE FROM message_search_fts")
        conn.execute("DELETE FROM sync_state")
        conn.commit()

    def search_by_domain(self, domain):
        """Find all emails from a specific domain."""
        normalized = (domain or "").strip().lower()
        if not normalized:
            return []
        cur = self.conn.execute(
            """SELECT DISTINCT
                      m.id, m.folder_id, m.subject, m.sender_name, m.sender_address,
                      m.received_datetime, m.is_read, m.has_attachments, m.body_preview,
                      m.importance, m.company_label
               FROM messages m
               LEFT JOIN message_recipients r ON r.message_id = m.id
               WHERE LOWER(COALESCE(m.sender_address, '')) LIKE ?
                  OR LOWER(COALESCE(r.recipient_address, '')) LIKE ?
               ORDER BY m.received_datetime DESC""",
            (f"%@{normalized}", f"%@{normalized}"),
        )
        return self._rows_to_messages(cur.fetchall())

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
        return self._rows_to_messages(cur.fetchall())

    def search_company_messages(self, query, search_text=None, limit=None):
        """Find messages matching company query semantics across sender and recipients."""
        normalized = (query or "").strip().lower()
        if not normalized:
            return []

        normalized_search = (search_text or "").strip().lower()
        if normalized_search:
            if self._is_fts_enabled():
                try:
                    return self._search_company_messages_fts(
                        normalized,
                        normalized_search,
                        limit=limit,
                    )
                except sqlite3.OperationalError as exc:
                    logger.warning("FTS search failed, falling back to LIKE: %s", exc)
            return self._search_company_messages_like(
                normalized,
                search_text=normalized_search,
                limit=limit,
            )
        return self._search_company_messages_like(normalized, limit=limit)

    def search_messages(self, search_text, folder_id=None, limit=None):
        """Search all cached messages by text across subject, body, sender, recipients."""
        normalized = (search_text or "").strip().lower()
        if not normalized:
            return []
        if self._is_fts_enabled():
            try:
                return self._search_messages_fts(normalized, folder_id, limit)
            except sqlite3.OperationalError as exc:
                logger.warning("FTS search failed, falling back to LIKE: %s", exc)
        return self._search_messages_like(normalized, folder_id, limit)

    def _search_messages_fts(self, search_text, folder_id=None, limit=None):
        fts_query = self._fts_query_from_text(search_text)
        if not fts_query:
            return self._search_messages_like(search_text, folder_id, limit)
        params = []
        folder_clause = ""
        if folder_id:
            folder_clause = " AND m.folder_id = ?"
            params.append(folder_id)
        params.append(fts_query)
        limit_clause = ""
        if limit is not None:
            limit_clause = "\n               LIMIT ?"
            params.append(int(limit))
        cur = self.conn.execute(
            f"""SELECT {self._BASE_MESSAGE_SELECT}
               FROM messages m
               JOIN message_search_fts f ON f.message_id = m.id
               WHERE 1=1{folder_clause}
                 AND message_search_fts MATCH ?
               ORDER BY m.received_datetime DESC{limit_clause}""",
            tuple(params),
        )
        return self._rows_to_messages(cur.fetchall())

    def _search_messages_like(self, search_text, folder_id=None, limit=None):
        like_value = f"%{search_text}%"
        params = [like_value, like_value, like_value, like_value, like_value, like_value, like_value]
        folder_clause = ""
        if folder_id:
            folder_clause = " AND m.folder_id = ?"
            params.append(folder_id)
        limit_clause = ""
        if limit is not None:
            limit_clause = "\n               LIMIT ?"
            params.append(int(limit))
        cur = self.conn.execute(
            f"""SELECT {self._BASE_MESSAGE_SELECT}
               FROM messages m
               WHERE (
                   LOWER(COALESCE(m.subject, '')) LIKE ?
                   OR LOWER(COALESCE(m.body_preview, '')) LIKE ?
                   OR LOWER(COALESCE(m.sender_name, '')) LIKE ?
                   OR LOWER(COALESCE(m.sender_address, '')) LIKE ?
                   OR EXISTS (
                       SELECT 1 FROM message_recipients sr
                       WHERE sr.message_id = m.id AND (
                           LOWER(COALESCE(sr.recipient_name, '')) LIKE ?
                           OR LOWER(COALESCE(sr.recipient_address, '')) LIKE ?
                       )
                   )
                   OR EXISTS (
                       SELECT 1 FROM message_bodies mb
                       WHERE mb.id = m.id AND LOWER(COALESCE(mb.content, '')) LIKE ?
                   )
               ){folder_clause}
               ORDER BY m.received_datetime DESC{limit_clause}""",
            tuple(params),
        )
        return self._rows_to_messages(cur.fetchall())

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

    def clear_delta_links(self):
        """Remove all stored delta links, forcing a full re-sync on next init."""
        self.conn.execute("DELETE FROM sync_state")
        self.conn.commit()

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
