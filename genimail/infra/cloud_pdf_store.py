import time


class CloudPdfStoreMixin:
    def get_cloud_pdf_entry(self, url_key):
        cur = self.conn.execute(
            """SELECT url_key, url, local_path, file_name, size_bytes, content_type,
                      source, content_hash, fetched_at, last_accessed_at
               FROM cloud_pdf_cache
               WHERE url_key = ?""",
            (url_key,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def upsert_cloud_pdf_entry(
        self,
        url_key,
        *,
        url,
        local_path,
        file_name,
        size_bytes,
        content_type,
        source,
        content_hash,
        fetched_at,
        last_accessed_at,
    ):
        self.conn.execute(
            """INSERT OR REPLACE INTO cloud_pdf_cache
               (url_key, url, local_path, file_name, size_bytes, content_type,
                source, content_hash, fetched_at, last_accessed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                url_key,
                url,
                local_path,
                file_name,
                int(size_bytes or 0),
                content_type,
                source,
                content_hash,
                int(fetched_at),
                int(last_accessed_at),
            ),
        )
        self.conn.commit()

    def touch_cloud_pdf_entry(self, url_key, last_accessed_at=None):
        self.conn.execute(
            "UPDATE cloud_pdf_cache SET last_accessed_at = ? WHERE url_key = ?",
            (int(last_accessed_at or time.time()), url_key),
        )
        self.conn.commit()

    def delete_cloud_pdf_entry(self, url_key):
        self.conn.execute("DELETE FROM cloud_pdf_cache WHERE url_key = ?", (url_key,))
        self.conn.commit()

    def list_cloud_pdf_entries(self):
        cur = self.conn.execute(
            """SELECT url_key, url, local_path, file_name, size_bytes, content_type,
                      source, content_hash, fetched_at, last_accessed_at
               FROM cloud_pdf_cache"""
        )
        return [dict(row) for row in cur.fetchall()]


__all__ = ["CloudPdfStoreMixin"]
