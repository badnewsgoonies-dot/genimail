import base64
import os
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from genimail.infra.document_store import open_document_file
from genimail.paths import PDF_DIR


class EmailAttachmentMixin:
    def _selected_attachment(self):
        item = self.attachment_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _select_attachment_by_id(self, attachment_id):
        if not attachment_id:
            return False
        for index in range(self.attachment_list.count()):
            item = self.attachment_list.item(index)
            data = item.data(Qt.UserRole) if item is not None else None
            if (data or {}).get("id") == attachment_id:
                self.attachment_list.setCurrentRow(index)
                return True
        return False

    def _on_thumbnail_clicked(self, attachment):
        if not attachment:
            return
        attachment_id = attachment.get("id")
        if self._select_attachment_by_id(attachment_id):
            self._open_selected_attachment()
            return

        message_id = (self.current_message or {}).get("id")
        if not message_id or not attachment_id:
            return
        self._set_status("Downloading attachment...")
        self.workers.submit(
            lambda: self._download_attachment_bytes(message_id, attachment_id),
            self._on_open_attachment_ready,
        )

    def _download_attachment_bytes(self, message_id, attachment_id):
        attachment = self.graph.download_attachment(message_id, attachment_id)
        encoded = attachment.get("contentBytes")
        if not encoded:
            raise RuntimeError("Attachment payload did not include content bytes.")
        return base64.b64decode(encoded), attachment.get("name") or "attachment.bin"

    def _open_selected_attachment(self):
        attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Select Attachment", "Select an attachment first.")
            return
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            return
        self._set_status("Downloading attachment...")
        self.workers.submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            self._on_open_attachment_ready,
        )

    def _on_open_attachment_ready(self, payload):
        payload_bytes, filename = payload
        os.makedirs(PDF_DIR, exist_ok=True)
        target_path = self._unique_output_path(PDF_DIR, filename)
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        lower = target_path.lower()
        if lower.endswith(".pdf"):
            self._open_pdf_file(target_path, activate=True)
        elif lower.endswith((".doc", ".docx")) and hasattr(self, "_open_doc_preview"):
            self._open_doc_preview(target_path, activate=True)
        else:
            open_document_file(target_path)
        self._set_status(f"Opened attachment: {os.path.basename(target_path)}")

    def _add_download_result_button(self, file_path):
        if not hasattr(self, "download_results_layout"):
            return
        filename = os.path.basename(file_path)
        btn = QPushButton(f"Open: {filename}")
        btn.setObjectName("downloadResultButton")
        btn.setToolTip(file_path)
        btn.clicked.connect(lambda _checked=False, p=file_path: (
            self._open_pdf_file(p, activate=True)
            if p.lower().endswith(".pdf")
            else (
                self._open_doc_preview(p, activate=True)
                if p.lower().endswith((".doc", ".docx")) and hasattr(self, "_open_doc_preview")
                else open_document_file(p)
            )
        ))
        layout = self.download_results_layout
        layout.insertWidget(layout.count() - 1, btn)
        self.download_results_widget.show()

    def _clear_download_results(self):
        if not hasattr(self, "download_results_layout"):
            return
        layout = self.download_results_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.download_results_widget.hide()

    def _save_selected_attachment(self):
        attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Select Attachment", "Select an attachment first.")
            return
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            return
        default_name = attachment.get("name") or "attachment.bin"
        target_path, _ = QFileDialog.getSaveFileName(self, "Save Attachment", default_name)
        if not target_path:
            return
        self._set_status("Saving attachment...")
        self.workers.submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            partial(self._on_save_attachment_ready, target_path=target_path),
        )

    def _on_save_attachment_ready(self, payload, target_path):
        payload_bytes, _ = payload
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        self._set_status(f"Saved attachment: {os.path.basename(target_path)}")


__all__ = ["EmailAttachmentMixin"]
