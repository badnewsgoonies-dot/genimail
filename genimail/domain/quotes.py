import os
import re
import shutil
import webbrowser
from datetime import datetime
from email.utils import parseaddr

from genimail.paths import DEFAULT_QUOTE_TEMPLATE_FILE, QUOTE_DIR


def ensure_default_quote_template(template_path: str):
    """Create a starter quote template if one does not exist."""
    if os.path.exists(template_path):
        return
    os.makedirs(os.path.dirname(template_path), exist_ok=True)
    starter = (
        "GX Painting LTD\n"
        "Quote #: {{QUOTE_ID}}\n"
        "Date: {{DATE}}\n"
        "\n"
        "Client: {{CLIENT_NAME}}\n"
        "Email: {{CLIENT_EMAIL}}\n"
        "Project: {{PROJECT_NAME}}\n"
        "Reference: {{EMAIL_SUBJECT}}\n"
        "\n"
        "Scope of Work:\n"
        "- [Describe the work]\n"
        "\n"
        "Pricing:\n"
        "- Labor: [Enter amount]\n"
        "- Materials: [Enter amount]\n"
        "- Total: [Enter amount]\n"
        "\n"
        "Notes:\n"
        "- [Add terms or timeline]\n"
        "\n"
        "Prepared by: GX Painting LTD\n"
    )
    with open(template_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(starter)


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


def create_quote_doc(template_path: str, output_dir: str, context: dict) -> str:
    template_path = os.path.abspath((template_path or "").strip() or DEFAULT_QUOTE_TEMPLATE_FILE)
    output_dir = os.path.abspath((output_dir or "").strip() or QUOTE_DIR)
    ensure_default_quote_template(template_path)
    os.makedirs(output_dir, exist_ok=True)

    client_name = context.get("client_name") or context.get("client_email") or "Client"
    client_slug = _sanitize_filename_part(client_name, fallback="Client")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(template_path, "rb") as f:
        template_bytes = f.read()

    template_ext = os.path.splitext(template_path)[1].lower()
    if template_bytes.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
        out_ext = ".doc"
    elif template_bytes.startswith(b"PK\x03\x04"):
        if template_ext in {".docx", ".docm", ".dotx", ".dotm"}:
            out_ext = template_ext
        else:
            out_ext = ".docx"
    else:
        out_ext = ".doc"

    out_path = os.path.join(output_dir, f"Quote_{stamp}_{client_slug}{out_ext}")

    if template_bytes.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
        shutil.copy2(template_path, out_path)
        return out_path
    if template_bytes.startswith(b"PK\x03\x04"):
        shutil.copy2(template_path, out_path)
        return out_path

    template_text = None
    for enc in ("utf-8-sig", "utf-16"):
        try:
            template_text = template_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if template_text is None:
        try:
            cp_text = template_bytes.decode("cp1252")
            printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in cp_text)
            if cp_text and printable / len(cp_text) > 0.9:
                template_text = cp_text
        except UnicodeDecodeError:
            pass

    if template_text is None:
        shutil.copy2(template_path, out_path)
        return out_path

    rendered = render_quote_template_text(template_text, context)
    with open(out_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(rendered)
    return out_path


def open_document_file(path: str) -> bool:
    target = os.path.abspath(path)
    try:
        os.startfile(target)
        return True
    except Exception:
        try:
            webbrowser.open(f"file:///{target.replace(os.sep, '/')}")
            return True
        except Exception:
            return False


def latest_doc_file(output_dir: str):
    if not output_dir or not os.path.isdir(output_dir):
        return None
    matches = []
    for name in os.listdir(output_dir):
        if name.lower().endswith(".doc"):
            full = os.path.join(output_dir, name)
            try:
                matches.append((os.path.getmtime(full), full))
            except OSError:
                pass
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]
