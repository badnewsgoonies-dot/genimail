import os
import time

from genimail.browser.downloads import DownloadResult
from genimail.infra.cache_store import EmailCache
from genimail_qt.cloud_pdf_cache import CloudPdfCache


def test_cloud_pdf_cache_reuses_fresh_entry(monkeypatch, tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    settings = {"cloud_pdf_cache_ttl_hours": 168, "cloud_pdf_cache_max_mb": 512}
    cloud_cache = CloudPdfCache(cache, lambda key, default=None: settings.get(key, default))
    cloud_cache.cache_dir = str(tmp_path / "cloud")
    os.makedirs(cloud_cache.cache_dir, exist_ok=True)

    calls = {"count": 0}

    def fake_download(url, timeout=(10, 45), allow_redirects=True):
        _ = timeout, allow_redirects
        calls["count"] += 1
        return DownloadResult(
            success=True,
            url=url,
            content=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
            status_code=200,
        )

    monkeypatch.setattr("genimail_qt.cloud_pdf_cache.download_url_content", fake_download)

    first = cloud_cache.acquire_pdf("https://example.com/a.pdf", "a.pdf", source="Test")
    second = cloud_cache.acquire_pdf("https://example.com/a.pdf", "a.pdf", source="Test")

    assert first.from_cache is False
    assert second.from_cache is True
    assert calls["count"] == 1
    assert os.path.isfile(first.path)


def test_cloud_pdf_cache_prunes_stale_entries(tmp_path):
    cache = EmailCache(db_path=str(tmp_path / "cache.db"))
    settings = {"cloud_pdf_cache_ttl_hours": 1, "cloud_pdf_cache_max_mb": 512}
    cloud_cache = CloudPdfCache(cache, lambda key, default=None: settings.get(key, default))
    cloud_cache.cache_dir = str(tmp_path / "cloud")
    os.makedirs(cloud_cache.cache_dir, exist_ok=True)

    stale_path = tmp_path / "cloud" / "stale.pdf"
    stale_path.write_bytes(b"%PDF-1.4\nstale")

    now = int(time.time())
    cache.upsert_cloud_pdf_entry(
        "k1",
        url="https://example.com/stale.pdf",
        local_path=str(stale_path),
        file_name="stale.pdf",
        size_bytes=stale_path.stat().st_size,
        content_type="application/pdf",
        source="Test",
        content_hash="x",
        fetched_at=now - 8_000,
        last_accessed_at=now - 8_000,
    )

    result = cloud_cache.prune()
    assert result["deleted"] >= 1
    assert cache.get_cloud_pdf_entry("k1") is None
