import base64
import os
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QDialog, QListWidgetItem

from genimail.browser import BrowserDownloadError
from genimail.constants import CLOUD_PDF_FAILURE_PREVIEW_MAX
from genimail.domain.quotes import open_document_file
from genimail.paths import PDF_DIR
from genimail_qt.dialogs import CloudPdfLinkDialog


class EmailAttachmentMixin:
    def _selected_attachment(self):
        item = self.attachment_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _selected_cloud_download(self):
        item = self.cloud_download_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _update_cloud_download_buttons(self, *_):
        self.open_cloud_download_btn.setEnabled(self.cloud_download_list.currentRow() >= 0)

    def _update_cloud_download_list(self, message_id):
        self.cloud_download_list.clear()
        if not message_id:
            self.cloud_download_label.hide()
            self.cloud_download_list.hide()
            self._update_cloud_download_buttons()
            return
        downloads = self.cloud_pdf_downloads.get(message_id, [])
        if not downloads:
            self.cloud_download_label.hide()
            self.cloud_download_list.hide()
            self._update_cloud_download_buttons()
            return
        self.cloud_download_label.show()
        self.cloud_download_list.show()
        for item in downloads:
            path = item.get("path")
            if not path:
                continue
            label = os.path.basename(path)
            if item.get("from_cache"):
                label = f"{label} · cached"
            entry = QListWidgetItem(label)
            entry.setData(Qt.UserRole, path)
            self.cloud_download_list.addItem(entry)
        self._update_cloud_download_buttons()

    def _open_selected_cloud_download(self):
        path = self._selected_cloud_download()
        if not path:
            QMessageBox.information(self, "Select Download", "Select a downloaded PDF first.")
            return
        self._open_download_path(path)

    def _open_download_path(self, path):
        if not path:
            return
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            self._open_pdf_file(path, activate=True)
        elif os.path.isfile(path):
            open_document_file(path)
        else:
            QMessageBox.warning(self, "File Missing", f"Could not find downloaded file:\n{path}")

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
        self._submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            self._on_open_attachment_ready,
        )

    def _on_open_attachment_ready(self, payload):
        payload_bytes, filename = payload
        os.makedirs(PDF_DIR, exist_ok=True)
        target_path = self._unique_output_path(PDF_DIR, filename)
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        if target_path.lower().endswith(".pdf"):
            self._open_pdf_file(target_path, activate=True)
        else:
            open_document_file(target_path)
        self._set_status(f"Opened attachment: {os.path.basename(target_path)}")

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
        self._submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            partial(self._on_save_attachment_ready, target_path=target_path),
        )

    def _on_save_attachment_ready(self, payload, target_path):
        payload_bytes, _ = payload
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        self._set_status(f"Saved attachment: {os.path.basename(target_path)}")

    def _open_cloud_links_for_current(self):
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            QMessageBox.information(self, "No Message", "Select a message first.")
            return
        links = self.cloud_link_cache.get(message_id) or []
        if not links:
            QMessageBox.information(self, "No Links", "No supported cloud PDF links found in this email.")
            return

        if len(links) == 1:
            selected_links = links
        else:
            dialog = CloudPdfLinkDialog(self, links)
            if dialog.exec() != QDialog.Accepted:
                return
            selected_links = dialog.selected_links()
            if not selected_links:
                return

        self._set_status(f"Opening {len(selected_links)} linked PDF(s)...")
        self._submit(
            lambda: self._download_cloud_links(message_id, selected_links),
            self._on_cloud_links_downloaded,
        )

    def _download_cloud_links(self, message_id, selected_links):
        opened_items = []
        failures = []
        for index, link in enumerate(selected_links, start=1):
            try:
                source = link.get("source", "External")
                suggested = link.get("suggested_name") or f"linked_{index}.pdf"
                result = self.cloud_pdf_cache.acquire_pdf(
                    link.get("download_url", ""),
                    suggested_name=suggested,
                    source=source,
                )
                opened_items.append({"path": result.path, "from_cache": result.from_cache})
            except (BrowserDownloadError, OSError, ValueError) as exc:
                failures.append(f"{link.get('source', 'External')}: {exc}")
        return {"message_id": message_id, "opened_items": opened_items, "failures": failures}

    def _on_cloud_links_downloaded(self, payload):
        message_id = payload.get("message_id")
        opened_items = payload.get("opened_items") or []
        failures = payload.get("failures") or []
        cache_hits = 0

        for idx, item in enumerate(opened_items):
            path = item.get("path")
            if not path:
                continue
            if item.get("from_cache"):
                cache_hits += 1
            self._open_pdf_file(path, activate=(idx == 0))

        if message_id and opened_items:
            downloads = self.cloud_pdf_downloads.get(message_id, [])
            existing_paths = {entry.get("path") for entry in downloads if entry.get("path")}
            for item in opened_items:
                if item.get("path") and item.get("path") not in existing_paths:
                    downloads.append(item)
            self.cloud_pdf_downloads[message_id] = downloads
            if (self.current_message or {}).get("id") == message_id:
                self._update_cloud_download_list(message_id)

        if opened_items:
            self.workspace_tabs.setCurrentWidget(self.pdf_tab)
            if cache_hits:
                self._set_status(f"Opened {len(opened_items)} linked PDF(s) · {cache_hits} from cache")
            else:
                self._set_status(f"Opened {len(opened_items)} linked PDF(s)")
        else:
            self._set_status("No linked PDFs opened")

        if failures:
            QMessageBox.warning(
                self,
                "Some Links Failed",
                "Could not open all selected links:\n\n"
                + "\n".join(failures[:CLOUD_PDF_FAILURE_PREVIEW_MAX]),
            )


__all__ = ["EmailAttachmentMixin"]
