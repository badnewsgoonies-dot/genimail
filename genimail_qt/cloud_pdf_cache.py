import hashlib
import os
import re
import time
from dataclasses import dataclass

from genimail.browser import download_url_content, require_pdf_bytes
from genimail.constants import (
    BYTES_PER_MB,
    CLOUD_PDF_CACHE_DEFAULT_MAX_MB,
    CLOUD_PDF_CACHE_DEFAULT_TTL_HOURS,
    CLOUD_PDF_CACHE_FILENAME_HASH_CHARS,
    CLOUD_PDF_CACHE_MAX_MB,
    CLOUD_PDF_CACHE_MAX_TTL_HOURS,
    CLOUD_PDF_CACHE_MIN_MB,
    CLOUD_PDF_CACHE_MIN_TTL_HOURS,
    CLOUD_PDF_CACHE_SAFE_FILENAME_MAX_CHARS,
    SECONDS_PER_HOUR,
)
from genimail.paths import PDF_DIR


def _safe_filename(name: str, fallback: str = "linked.pdf") -> str:
    value = (name or "").strip() or fallback
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = " ".join(value.split()).strip()
    if not value:
        value = fallback
    if not value.lower().endswith(".pdf"):
        value += ".pdf"
    if len(value) <= CLOUD_PDF_CACHE_SAFE_FILENAME_MAX_CHARS:
        return value
    base, ext = os.path.splitext(value)
    max_base_len = max(1, CLOUD_PDF_CACHE_SAFE_FILENAME_MAX_CHARS - len(ext))
    return f"{base[:max_base_len]}{ext}"


def url_key(url: str) -> str:
    return hashlib.sha256((url or "").strip().lower().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CacheAcquireResult:
    path: str
    from_cache: bool
    url: str


class CloudPdfCache:
    def __init__(self, cache_store, config_get):
        self.cache = cache_store
        self.config_get = config_get
        self.cache_dir = os.path.join(PDF_DIR, "cloud_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _ttl_seconds(self) -> int:
        raw = self.config_get("cloud_pdf_cache_ttl_hours", CLOUD_PDF_CACHE_DEFAULT_TTL_HOURS)
        try:
            hours = int(raw)
        except (TypeError, ValueError):
            hours = CLOUD_PDF_CACHE_DEFAULT_TTL_HOURS
        hours = max(CLOUD_PDF_CACHE_MIN_TTL_HOURS, min(hours, CLOUD_PDF_CACHE_MAX_TTL_HOURS))
        return hours * SECONDS_PER_HOUR

    def _max_cache_bytes(self) -> int:
        raw = self.config_get("cloud_pdf_cache_max_mb", CLOUD_PDF_CACHE_DEFAULT_MAX_MB)
        try:
            mb = int(raw)
        except (TypeError, ValueError):
            mb = CLOUD_PDF_CACHE_DEFAULT_MAX_MB
        mb = max(CLOUD_PDF_CACHE_MIN_MB, min(mb, CLOUD_PDF_CACHE_MAX_MB))
        return mb * BYTES_PER_MB

    def _build_cached_path(self, url: str, suggested_name: str) -> str:
        key = url_key(url)
        base = os.path.splitext(_safe_filename(suggested_name))[0]
        filename = f"{base}_{key[:CLOUD_PDF_CACHE_FILENAME_HASH_CHARS]}.pdf"
        return os.path.join(self.cache_dir, filename)

    def get_entry(self, url: str):
        key = url_key(url)
        row = self.cache.get_cloud_pdf_entry(key)
        if not row:
            return None
        local_path = row.get("local_path") or ""
        if not local_path or not os.path.isfile(local_path):
            self.cache.delete_cloud_pdf_entry(key)
            return None
        return row

    def is_fresh(self, entry: dict, now_ts: int | None = None) -> bool:
        if not entry:
            return False
        now_value = int(now_ts or time.time())
        fetched_at = int(entry.get("fetched_at") or 0)
        return (now_value - fetched_at) <= self._ttl_seconds()

    def acquire_pdf(self, url: str, suggested_name: str, source: str = "External") -> CacheAcquireResult:
        now_ts = int(time.time())
        entry = self.get_entry(url)
        if entry and self.is_fresh(entry, now_ts=now_ts):
            key = url_key(url)
            self.cache.touch_cloud_pdf_entry(key, now_ts)
            return CacheAcquireResult(path=entry["local_path"], from_cache=True, url=url)

        download = download_url_content(url)
        content = require_pdf_bytes(download)
        target_path = self._build_cached_path(url, suggested_name)

        old_path = entry.get("local_path") if entry else None
        with open(target_path, "wb") as handle:
            handle.write(content)

        key = url_key(url)
        self.cache.upsert_cloud_pdf_entry(
            key,
            url=url,
            local_path=target_path,
            file_name=os.path.basename(target_path),
            size_bytes=len(content),
            content_type=download.content_type or "application/pdf",
            source=source,
            content_hash=hashlib.sha256(content).hexdigest(),
            fetched_at=now_ts,
            last_accessed_at=now_ts,
        )

        if old_path and old_path != target_path and os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

        self.prune()
        return CacheAcquireResult(path=target_path, from_cache=False, url=url)

    def prune(self) -> dict:
        now_ts = int(time.time())
        max_age = self._ttl_seconds()
        max_bytes = self._max_cache_bytes()
        entries = self.cache.list_cloud_pdf_entries()
        deleted = 0
        reclaimed_bytes = 0

        stale = [
            row for row in entries
            if (now_ts - int(row.get("fetched_at") or 0)) > max_age
            or not os.path.isfile(row.get("local_path") or "")
        ]
        for row in stale:
            reclaimed_bytes += int(row.get("size_bytes") or 0)
            self.cache.delete_cloud_pdf_entry(row["url_key"])
            local_path = row.get("local_path") or ""
            if local_path and os.path.isfile(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass
            deleted += 1

        remaining = self.cache.list_cloud_pdf_entries()
        total_bytes = sum(int(row.get("size_bytes") or 0) for row in remaining)
        if total_bytes > max_bytes:
            ordered = sorted(remaining, key=lambda row: int(row.get("last_accessed_at") or 0))
            for row in ordered:
                if total_bytes <= max_bytes:
                    break
                size = int(row.get("size_bytes") or 0)
                total_bytes -= size
                reclaimed_bytes += size
                self.cache.delete_cloud_pdf_entry(row["url_key"])
                local_path = row.get("local_path") or ""
                if local_path and os.path.isfile(local_path):
                    try:
                        os.remove(local_path)
                    except OSError:
                        pass
                deleted += 1

        return {"deleted": deleted, "reclaimed_bytes": reclaimed_bytes}
