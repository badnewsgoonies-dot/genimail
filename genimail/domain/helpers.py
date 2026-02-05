import hashlib
import html
import os
import re
from datetime import datetime

from genimail.constants import (
    BYTES_PER_KB,
    BYTES_PER_MB,
    CM_PER_INCH,
    DEFAULT_CLIENT_ID,
    INCHES_PER_FOOT,
    INCHES_PER_METER,
    MM_PER_INCH,
    TOKEN_CACHE_ID_HASH_CHARS,
)
from genimail.paths import CONFIG_DIR, TOKEN_CACHE_FILE

UNIT_CHOICES = ("ft", "in", "mm", "cm", "m")


def parse_length_to_inches(raw: str, default_unit: str = "in") -> float:
    """Parse user-entered lengths into inches."""
    if raw is None:
        raise ValueError("Missing length.")
    s = raw.strip().lower()
    if not s:
        raise ValueError("Missing length.")

    s = s.replace("feet", "ft").replace("foot", "ft").replace("inches", "in").replace("inch", "in")
    s = s.replace("millimeters", "mm").replace("millimeter", "mm")
    s = s.replace("centimeters", "cm").replace("centimeter", "cm")
    s = s.replace("meters", "m").replace("meter", "m")
    s = s.replace("”", "\"").replace("“", "\"").replace("′", "'").replace("″", "\"")
    s = " ".join(s.split())

    def _unit_value_to_inches(value: float, unit: str) -> float:
        if unit == "in":
            return value
        if unit == "ft":
            return value * INCHES_PER_FOOT
        if unit == "mm":
            return value / MM_PER_INCH
        if unit == "cm":
            return value / CM_PER_INCH
        if unit == "m":
            return value * INCHES_PER_METER
        raise ValueError(f"Unsupported unit: {unit}")

    if "'" in s:
        left, right = s.split("'", 1)
        feet = float(left.strip() or "0")
        right = right.strip()
        inches = 0.0
        if right:
            right = right.replace('"', "").replace("in", "").strip()
            if right:
                inches = float(right)
        return feet * INCHES_PER_FOOT + inches

    if "ft" in s:
        parts = s.split("ft", 1)
        feet = float(parts[0].strip() or "0")
        rest = parts[1].strip()
        inches = 0.0
        if rest:
            rest = rest.replace("in", "").replace('"', "").strip()
            if rest:
                inches = float(rest)
        return feet * INCHES_PER_FOOT + inches

    unit_re = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*(mm|cm|ft|in|m)')
    matches = list(unit_re.finditer(s))
    if matches:
        consumed = unit_re.sub("", s)
        consumed = consumed.replace(",", " ").strip()
        if consumed:
            raise ValueError(f"Could not parse length: {raw}")
        total_inches = 0.0
        for match in matches:
            total_inches += _unit_value_to_inches(float(match.group(1)), match.group(2))
        return total_inches

    value = float(s)
    unit = (default_unit or "in").strip().lower()
    if unit not in UNIT_CHOICES:
        unit = "in"
    return _unit_value_to_inches(value, unit)


def token_cache_path_for_client_id(client_id: str) -> str:
    """Return a stable token cache path per client id."""
    cid = (client_id or DEFAULT_CLIENT_ID).strip()
    if cid == DEFAULT_CLIENT_ID:
        return TOKEN_CACHE_FILE
    digest = hashlib.sha1(cid.encode("utf-8")).hexdigest()[:TOKEN_CACHE_ID_HASH_CHARS]
    return os.path.join(CONFIG_DIR, f"token_cache_{digest}.json")


def strip_html(text):
    """Strip HTML tags, CSS, scripts and decode entities to plain text."""
    if not text:
        return ""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<!\[CDATA\[.*?\]\]>", "", text, flags=re.DOTALL)
    text = re.sub(r"<img[^>]*alt=[\"']([^\"']*)[\"'][^>]*>", r"[Image: \1]", text, flags=re.IGNORECASE)
    text = re.sub(r"<img[^>]*>", "[Image]", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.IGNORECASE)
    text = re.sub(r"<tr[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<td[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<th[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<a[^>]*href=[\"']([^\"']*)[\"'][^>]*>([^<]*)</a>", r"\2 [\1]", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    invisible_chars = "\u200b\u200c\u200d\ufeff\u00ad\u034f\u2060\u2061\u2062\u2063\u2064\u115f\u1160\u17b4\u17b5\u180e\u2800"
    for char in invisible_chars:
        text = text.replace(char, "")
    lines = text.split("\n")
    cleaned = []
    prev_blank = False
    for line in lines:
        stripped = " ".join(line.split())
        if not stripped:
            if not prev_blank:
                cleaned.append("")
                prev_blank = True
        else:
            cleaned.append(stripped)
            prev_blank = False
    return "\n".join(cleaned).strip()


def domain_to_company(domain):
    """Convert email domain to a readable company name."""
    if not domain:
        return "Other"
    parts = domain.lower().split(".")
    name = parts[-2] if len(parts) >= 2 else parts[0]
    skip = {"gmail", "yahoo", "hotmail", "outlook", "live", "msn", "aol", "icloud", "mail", "protonmail"}
    if name in skip:
        return domain.lower()
    return name.replace("-", " ").replace("_", " ").title()


def format_date(iso_str):
    """Format ISO date string for display."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%I:%M %p").lstrip("0")
        if dt.year == now.year:
            return dt.strftime("%b %d")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_str[:10] if iso_str else ""


def format_size(size_bytes):
    """Format file size for display."""
    if not size_bytes:
        return ""
    if size_bytes < BYTES_PER_KB:
        return f"{size_bytes} B"
    if size_bytes < BYTES_PER_MB:
        return f"{size_bytes / BYTES_PER_KB:.1f} KB"
    return f"{size_bytes / BYTES_PER_MB:.1f} MB"


def build_reply_recipients(reply_msg, current_user_email="", include_all=False):
    """Build To/CC recipient lists for reply or reply-all composition."""
    sender = (reply_msg or {}).get("from", {}).get("emailAddress", {})
    sender_addr = (sender.get("address") or "").strip()
    current_user = (current_user_email or "").strip().lower()

    to_recipients = []
    cc_recipients = []
    seen_to = set()

    def _add_to(address):
        addr = (address or "").strip()
        if not addr:
            return
        key = addr.lower()
        if current_user and key == current_user:
            return
        if key in seen_to:
            return
        seen_to.add(key)
        to_recipients.append(addr)

    _add_to(sender_addr)

    if include_all:
        for recipient in (reply_msg or {}).get("toRecipients", []):
            _add_to(recipient.get("emailAddress", {}).get("address"))

        seen_cc = set(seen_to)
        for recipient in (reply_msg or {}).get("ccRecipients", []):
            addr = (recipient.get("emailAddress", {}).get("address") or "").strip()
            if not addr:
                continue
            key = addr.lower()
            if current_user and key == current_user:
                continue
            if key in seen_cc:
                continue
            seen_cc.add(key)
            cc_recipients.append(addr)

    return to_recipients, cc_recipients
