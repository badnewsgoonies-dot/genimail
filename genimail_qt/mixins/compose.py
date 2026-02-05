from PySide6.QtWidgets import QMessageBox

from genimail.domain.helpers import build_reply_recipients, strip_html
from genimail_qt.compose_dialog import ComposeDialog


class ComposeMixin:
    def _open_compose_dialog(self, mode):
        if mode != "new" and not self.current_message:
            QMessageBox.information(self, "Select Message", "Select a message first.")
            return
        defaults = self._compose_defaults(mode)
        mode_label = {
            "new": "New Email",
            "reply": "Reply",
            "reply_all": "Reply All",
            "forward": "Forward",
        }.get(mode, "Compose")
        dialog = ComposeDialog(self, mode_label, defaults, self._start_send_from_dialog)
        dialog.exec()

    def _compose_defaults(self, mode):
        if mode == "new" or not self.current_message:
            return {"to": "", "cc": "", "subject": "", "body": ""}
        detail = self.message_cache.get(self.current_message.get("id"), self.current_message)
        subject = detail.get("subject") or ""
        sender_name = detail.get("from", {}).get("emailAddress", {}).get("name") or ""
        sender_addr = detail.get("from", {}).get("emailAddress", {}).get("address") or ""
        date_text = detail.get("receivedDateTime", "")
        body = detail.get("body", {}).get("content") or detail.get("bodyPreview") or ""
        if detail.get("body", {}).get("contentType", "").lower() == "html":
            body = strip_html(body)
        quoted = (
            "\n\n"
            f"--- Original message ---\n"
            f"From: {sender_name} <{sender_addr}>\n"
            f"Date: {date_text}\n"
            f"Subject: {subject}\n\n"
            f"{body}"
        )

        if mode == "forward":
            return {"to": "", "cc": "", "subject": f"FW: {subject}", "body": quoted}

        include_all = mode == "reply_all"
        to_list, cc_list = build_reply_recipients(
            detail,
            current_user_email=self.current_user_email,
            include_all=include_all,
        )
        return {
            "to": "; ".join(to_list),
            "cc": "; ".join(cc_list),
            "subject": f"RE: {subject}",
            "body": quoted,
        }

    def _start_send_from_dialog(self, payload, dialog):
        if not self.graph:
            dialog.mark_send_failed("Not connected.")
            return
        self._set_status("Sending email...")
        self.workers.submit(
            lambda: self._send_mail_worker(payload),
            lambda _: self._on_send_completed(dialog),
            lambda err: dialog.mark_send_failed(err),
        )

    def _send_mail_worker(self, payload):
        self.graph.send_mail(
            payload["to"],
            payload["cc"],
            payload["subject"],
            payload["body"],
            attachments=payload["attachments"],
        )
        return True

    def _on_send_completed(self, dialog):
        self._set_status("Email sent")
        QMessageBox.information(self, "Sent", "Email sent successfully.")
        dialog.accept()


__all__ = ["ComposeMixin"]
