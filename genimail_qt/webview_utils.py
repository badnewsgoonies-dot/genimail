from urllib.parse import unquote

from genimail_qt.constants import CID_SRC_PATTERN, JS_NOISE_PATTERNS, LOCAL_JS_SOURCE_PREFIXES


def is_js_noise_message(message):
    lowered = (message or "").lower()
    if not lowered:
        return False
    return any(pattern in lowered for pattern in JS_NOISE_PATTERNS)


def is_local_console_source(source_id):
    lowered = (source_id or "").lower()
    if not lowered:
        return False
    return lowered.startswith(LOCAL_JS_SOURCE_PREFIXES)


def normalize_cid_value(value):
    cid = (value or "").strip()
    if not cid:
        return ""
    cid = unquote(cid).strip()
    if cid.lower().startswith("cid:"):
        cid = cid[4:]
    cid = cid.strip("<> ").lower()
    return cid


def replace_cid_sources_with_data_urls(html_content, cid_data_urls):
    if not html_content or not cid_data_urls:
        return html_content

    def _replace(match):
        raw_cid = match.group(1)
        normalized = normalize_cid_value(raw_cid)
        return cid_data_urls.get(normalized, match.group(0))

    return CID_SRC_PATTERN.sub(_replace, html_content)


def is_inline_attachment(attachment):
    return bool(attachment.get("isInline"))


__all__ = [
    "is_inline_attachment",
    "is_js_noise_message",
    "is_local_console_source",
    "normalize_cid_value",
    "replace_cid_sources_with_data_urls",
]
