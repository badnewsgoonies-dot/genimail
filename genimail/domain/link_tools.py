import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


URL_RE = re.compile(r"https?://[^\s<>'\"()]+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    urls = []
    seen = set()
    for match in URL_RE.finditer(text):
        value = match.group(0).rstrip(".,;!?")
        if value and value not in seen:
            seen.add(value)
            urls.append(value)
    return urls


def link_source_label(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if "drive.google.com" in host or "docs.google.com" in host:
        return "Google Drive"
    if "dropbox.com" in host:
        return "Dropbox"
    if "1drv.ms" in host or "onedrive.live.com" in host:
        return "OneDrive"
    return host or "External"


def normalize_cloud_download_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query, keep_blank_values=True)

    if "dropbox.com" in host:
        query["dl"] = ["1"]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    if "drive.google.com" in host:
        file_match = re.search(r"/file/d/([^/]+)", path)
        if file_match:
            file_id = file_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        if path.startswith("/uc"):
            query["export"] = ["download"]
            return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    if "docs.google.com" in host:
        doc_match = re.search(r"/document/d/([^/]+)", path)
        if doc_match:
            doc_id = doc_match.group(1)
            return f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
        sheet_match = re.search(r"/spreadsheets/d/([^/]+)", path)
        if sheet_match:
            sheet_id = sheet_match.group(1)
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=pdf"
        slide_match = re.search(r"/presentation/d/([^/]+)", path)
        if slide_match:
            slide_id = slide_match.group(1)
            return f"https://docs.google.com/presentation/d/{slide_id}/export/pdf"

    return url


def is_supported_cloud_link(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(
        provider in host
        for provider in ("drive.google.com", "docs.google.com", "dropbox.com", "1drv.ms", "onedrive.live.com")
    )


def suggest_pdf_name(url: str, index: int = 1) -> str:
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path or "").strip()
    if not filename:
        filename = f"linked_{index}.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return filename


def collect_cloud_pdf_links(raw_html: str, plain_text: str) -> list[dict]:
    candidates = []
    seen = set()

    for url in [*extract_urls(raw_html), *extract_urls(plain_text)]:
        normalized = normalize_cloud_download_url(url)
        parsed = urlparse(normalized)
        path = (parsed.path or "").lower()
        query = (parsed.query or "").lower()
        looks_pdf = path.endswith(".pdf") or "format=pdf" in query
        if not (is_supported_cloud_link(url) or looks_pdf):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "source": link_source_label(url),
                "original_url": url,
                "download_url": normalized,
                "suggested_name": suggest_pdf_name(normalized, index=len(candidates) + 1),
            }
        )
    return candidates
