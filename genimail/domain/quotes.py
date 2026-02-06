"""Pure business logic for quote generation.

I/O operations (file read/write, template creation, document opening) live in
``genimail.infra.document_store``.
"""

import re
from datetime import datetime
from email.utils import parseaddr


def _sanitize_filename_part(value: str, fallback: str = "Quote") -> str:
    base = (value or "").strip()
    if not base:
        base = fallback
    base = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', " ", base)
    base = " ".join(base.split()).strip()
    return base[:40] if base else fallback


def build_quote_context(reply_msg=None, to_value: str = "", subject_value: str = "") -> dict:
    sender = (reply_msg or {}).get("from", {}).get("emailAddress", {})
    client_email = to_value.strip() or sender.get("address", "")
    client_name = sender.get("name", "")
    if not client_name and client_email:
        parsed_name, parsed_email = parseaddr(client_email)
        if parsed_name:
            client_name = parsed_name
        elif parsed_email:
            client_name = parsed_email
    if not client_name:
        client_name = "[Client Name]"
    return {
        "quote_id": datetime.now().strftime("Q%Y%m%d-%H%M%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client_name": client_name,
        "client_email": client_email or "[Client Email]",
        "project_name": subject_value.strip() or "[Project Name]",
        "email_subject": subject_value.strip() or "[Email Subject]",
    }


def render_quote_template_text(template_text: str, context: dict) -> str:
    mapping = {
        "QUOTE_ID": context.get("quote_id", ""),
        "DATE": context.get("date", ""),
        "CLIENT_NAME": context.get("client_name", ""),
        "CLIENT_EMAIL": context.get("client_email", ""),
        "PROJECT_NAME": context.get("project_name", ""),
        "EMAIL_SUBJECT": context.get("email_subject", ""),
    }
    rendered = template_text
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered
