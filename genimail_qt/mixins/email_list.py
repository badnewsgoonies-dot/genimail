from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidgetItem, QMessageBox, QPushButton

from genimail.browser.navigation import ensure_light_preview_html, wrap_plain_text_as_html
from genimail.constants import (
    CLOUD_PDF_SOURCE_SUMMARY_MAX,
    EMAIL_LIST_FETCH_TOP,
)
from genimail.domain.helpers import format_date, format_size, strip_html
from genimail.domain.link_tools import collect_cloud_pdf_links
from genimail_qt.constants import ATTACHMENT_THUMBNAIL_MAX_INITIAL, ATTACHMENT_THUMBNAIL_NAME_MAX_CHARS
from genimail_qt.webview_utils import (
    is_inline_attachment,
    normalize_cid_value,
    replace_cid_sources_with_data_urls,
)


class EmailListMixin:
    def _load_messages(self):
        if not self.graph:
            QMessageBox.information(self, "Connect First", "Connect to Microsoft before loading messages.")
            return

        if self.company_filter_domain:
            search_text = self.search_input.text().strip() or None
            if search_text:
                self._load_company_messages_with_search(self.company_filter_domain, search_text)
            else:
                self._apply_company_folder_filter()
            return

        search_text = self.search_input.text().strip() or None
        folder_id = self.current_folder_id
        self._company_search_override = None
        self._message_load_token = getattr(self, "_message_load_token", 0) + 1
        load_token = self._message_load_token
        self._show_message_list()
        self._set_status("Loading messages...")
        self.workers.submit(
            lambda fid=folder_id, text=search_text, token=load_token: self._messages_worker(fid, text, token),
            self._on_messages_loaded,
        )

    def _messages_worker(self, folder_id, search_text, token):
        try:
            messages, _ = self.graph.get_messages(
                folder_id=folder_id,
                top=EMAIL_LIST_FETCH_TOP,
                search=search_text,
            )
        except Exception:
            if not search_text:
                raise
            # Graph search can fail for some folders/tenants. Fall back to local filtering.
            messages, _ = self.graph.get_messages(folder_id=folder_id, top=EMAIL_LIST_FETCH_TOP)
            search_lower = search_text.strip().lower()
            messages = [msg for msg in (messages or []) if self._message_matches_search(msg, search_lower)]
        return {"token": token, "folder_id": folder_id, "messages": messages or []}

    def _on_messages_loaded(self, payload):
        if isinstance(payload, dict):
            token = payload.get("token")
            if token is not None and token != getattr(self, "_message_load_token", token):
                return
            folder_id = payload.get("folder_id") or self.current_folder_id
            messages = payload.get("messages") or []
        else:
            folder_id = self.current_folder_id
            messages = payload or []

        folder_key = self._folder_key_for_id(folder_id)
        self.company_result_messages = []
        self._company_search_override = None
        self.current_messages = [self._with_folder_meta(msg, folder_id, folder_key) for msg in messages]
        self.known_ids = {msg.get("id") for msg in self.current_messages if msg.get("id")}
        self._refresh_company_sidebar()
        self._render_message_list()
        self._set_status(f"Loaded {len(self.filtered_messages)} of {len(self.current_messages)} messages")
        if self.message_list.count() > 0:
            self.message_list.setCurrentRow(0)
            self._show_message_list()
        else:
            self._show_message_list()
            self._clear_detail_view("No messages in this folder.")
        self._ensure_detail_message_visible()

    # ------------------------------------------------------------------
    # Helpers shared with CompanySearchMixin
    # ------------------------------------------------------------------

    @staticmethod
    def _message_matches_search(msg, search_text):
        sender = msg.get("from", {}).get("emailAddress", {})
        haystack = " ".join(
            [
                (msg.get("subject") or ""),
                (msg.get("bodyPreview") or ""),
                (sender.get("name") or ""),
                (sender.get("address") or ""),
            ]
        ).lower()
        return search_text in haystack

    @staticmethod
    def _with_folder_meta(msg, folder_id, folder_key, folder_label=None):
        enriched = dict(msg or {})
        enriched["_folder_id"] = folder_id
        enriched["_folder_key"] = folder_key
        enriched["_folder_label"] = folder_label or folder_key
        return enriched

    def _folder_key_for_id(self, folder_id):
        target_id = (folder_id or "").strip().lower()
        for source in self.company_folder_sources or []:
            if (source.get("id") or "").strip().lower() == target_id:
                return source.get("key") or target_id
        return target_id

    # ------------------------------------------------------------------
    # Message list rendering
    # ------------------------------------------------------------------

    def _render_message_list(self):
        self.filtered_messages = list(self.current_messages)
        self.message_list.clear()
        for msg in self.filtered_messages:
            sender = msg.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
            subject = msg.get("subject") or "(No subject)"
            received = format_date(msg.get("receivedDateTime", ""))
            unread_prefix = "● " if not msg.get("isRead") else ""
            preview = self._summarize_preview(msg.get("bodyPreview", ""))
            line = f"{unread_prefix}{subject}\n{sender} · {received} · {preview}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, msg)
            self.message_list.addItem(item)

    # ------------------------------------------------------------------
    # Message selection and detail
    # ------------------------------------------------------------------

    def _on_message_row_changed(self, row):
        if row < 0:
            self.current_message = None
            return
        item = self.message_list.item(row)
        if item is None:
            return
        self.current_message = item.data(Qt.UserRole) or {}

    def _on_message_opened(self, item):
        if item is None:
            return
        self._open_message_row(self.message_list.row(item))

    def _on_message_selected(self, row):
        self._open_message_row(row)

    def _open_message_row(self, row):
        if row < 0:
            return
        item = self.message_list.item(row)
        if item is None:
            return
        msg = item.data(Qt.UserRole) or {}
        self.current_message = msg
        message_id = msg.get("id")
        if not message_id:
            return
        self.message_header.setText("Loading message...")
        self._show_message_detail()
        if message_id in self.message_cache:
            self._render_message_detail(
                self.message_cache[message_id],
                self.attachment_cache.get(message_id, []),
                self.cloud_link_cache.get(message_id, []),
            )
            return
        self.workers.submit(
            lambda: self._fetch_message_detail(message_id),
            self._on_message_detail_loaded,
        )

    def _hydrate_inline_attachment_bytes(self, message_id, attachments):
        hydrated = []
        for attachment in attachments or []:
            file_type = attachment.get("@odata.type") == "#microsoft.graph.fileAttachment"
            inline = bool(attachment.get("isInline"))
            cid = normalize_cid_value(attachment.get("contentId") or attachment.get("contentLocation"))
            if not (file_type and inline and cid):
                hydrated.append(attachment)
                continue
            if attachment.get("contentBytes"):
                hydrated.append(attachment)
                continue
            attachment_id = attachment.get("id")
            if not attachment_id:
                hydrated.append(attachment)
                continue
            try:
                full_attachment = self.graph.download_attachment(message_id, attachment_id)
                merged = dict(attachment)
                if full_attachment.get("contentBytes"):
                    merged["contentBytes"] = full_attachment.get("contentBytes")
                if full_attachment.get("contentType"):
                    merged["contentType"] = full_attachment.get("contentType")
                if full_attachment.get("name"):
                    merged["name"] = full_attachment.get("name")
                hydrated.append(merged)
            except Exception:
                hydrated.append(attachment)
        return hydrated

    def _build_inline_cid_data_urls(self, attachments):
        cid_map = {}
        for attachment in attachments or []:
            file_type = attachment.get("@odata.type") == "#microsoft.graph.fileAttachment"
            cid = normalize_cid_value(attachment.get("contentId") or attachment.get("contentLocation"))
            content_bytes = attachment.get("contentBytes")
            if not (file_type and cid and content_bytes):
                continue
            mime_type = (attachment.get("contentType") or "application/octet-stream").strip()
            cid_map[cid] = f"data:{mime_type};base64,{content_bytes}"
        return cid_map

    def _fetch_message_detail(self, message_id):
        detail = self.graph.get_message(message_id)
        attachments = self.graph.get_attachments(message_id)
        attachments = self._hydrate_inline_attachment_bytes(message_id, attachments)
        body = detail.get("body", {})
        content_type = (body.get("contentType") or "").lower()
        content = body.get("content") or ""
        plain_text = strip_html(content) if content_type == "html" else (content or detail.get("bodyPreview", ""))
        cloud_links = collect_cloud_pdf_links(content if content_type == "html" else "", plain_text)
        self.cache.save_message_body(message_id, body.get("contentType", ""), body.get("content", ""))
        self.cache.save_attachments(message_id, attachments)
        return {"id": message_id, "detail": detail, "attachments": attachments, "cloud_links": cloud_links}

    def _on_message_detail_loaded(self, payload):
        message_id = payload.get("id")
        detail = payload.get("detail") or {}
        attachments = payload.get("attachments") or []
        cloud_links = payload.get("cloud_links") or []
        if message_id:
            self.message_cache[message_id] = detail
            self.attachment_cache[message_id] = attachments
            self.cloud_link_cache[message_id] = cloud_links
        if message_id and message_id != (self.current_message or {}).get("id"):
            return
        self._render_message_detail(detail, attachments, cloud_links)

    def _render_message_detail(self, detail, attachments, cloud_links=None):
        sender = detail.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
        address = detail.get("from", {}).get("emailAddress", {}).get("address") or ""
        received = format_date(detail.get("receivedDateTime", ""))
        subject = detail.get("subject") or "(No subject)"
        self.message_header.setText(f"{subject}\nFrom: {sender} <{address}> · {received}")

        body = detail.get("body", {}) or {}
        content_type = (body.get("contentType") or "").lower()
        content = body.get("content") or ""
        if content_type == "html":
            html_content = ensure_light_preview_html(content)
            html_content = replace_cid_sources_with_data_urls(
                html_content,
                self._build_inline_cid_data_urls(attachments),
            )
        else:
            clean_text = strip_html(content) if content else detail.get("bodyPreview", "")
            html_content = wrap_plain_text_as_html(clean_text)
        self.email_preview.setHtml(html_content)

        self.attachment_list.clear()
        visible_attachments = []
        for attachment in attachments:
            if is_inline_attachment(attachment):
                continue
            if attachment.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            visible_attachments.append(attachment)
            name = attachment.get("name") or "attachment"
            size_text = format_size(attachment.get("size") or 0)
            item = QListWidgetItem(f"{name}  ({size_text})")
            item.setData(Qt.UserRole, attachment)
            self.attachment_list.addItem(item)
        if self.attachment_list.count() > 0:
            self.attachment_list.setCurrentRow(0)
        self._render_attachment_thumbnails(visible_attachments)

        cloud_links = cloud_links or []
        self.open_cloud_links_btn.setEnabled(bool(cloud_links))
        if cloud_links:
            sources = sorted({link.get("source", "External") for link in cloud_links})
            summary = ", ".join(sources[:CLOUD_PDF_SOURCE_SUMMARY_MAX]) + (
                "..." if len(sources) > CLOUD_PDF_SOURCE_SUMMARY_MAX else ""
            )
            self.cloud_links_info.setText(f"{len(cloud_links)} linked cloud file(s) detected · {summary}")
        else:
            self.cloud_links_info.setText("No linked cloud files found")
        detail_id = detail.get("id") or (self.current_message or {}).get("id")
        self._update_cloud_download_list(detail_id)

    # ------------------------------------------------------------------
    # Attachment thumbnails
    # ------------------------------------------------------------------

    def _render_attachment_thumbnails(self, attachments):
        if not hasattr(self, "thumbnail_layout"):
            return
        while self.thumbnail_layout.count() > 1:
            item = self.thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible_attachments = [attachment for attachment in attachments if attachment]
        if not visible_attachments:
            self.attach_container.hide()
            return

        self.attach_container.show()
        for attachment in visible_attachments[:ATTACHMENT_THUMBNAIL_MAX_INITIAL]:
            thumb = self._create_attachment_thumbnail_button(attachment)
            self.thumbnail_layout.insertWidget(self.thumbnail_layout.count() - 1, thumb)

        if len(visible_attachments) > ATTACHMENT_THUMBNAIL_MAX_INITIAL:
            overflow_count = len(visible_attachments) - ATTACHMENT_THUMBNAIL_MAX_INITIAL
            more_label = QLabel(f"+{overflow_count} more")
            more_label.setObjectName("attachmentThumbnailOverflow")
            self.thumbnail_layout.insertWidget(self.thumbnail_layout.count() - 1, more_label)

    def _create_attachment_thumbnail_button(self, attachment):
        name = attachment.get("name") or "attachment"
        mime_type = (attachment.get("contentType") or "").lower()
        size_text = format_size(attachment.get("size") or 0)
        short_name = self._truncate_attachment_name(name)
        icon_text = self._attachment_type_label(mime_type)

        button = QPushButton(f"[{icon_text}]\\n{short_name}")
        button.setObjectName("attachmentThumbnail")
        button.setToolTip(f"{name} ({size_text})")
        button.clicked.connect(lambda _checked=False, att=attachment: self._on_thumbnail_clicked(att))
        return button

    @staticmethod
    def _attachment_type_label(mime_type):
        if "pdf" in mime_type:
            return "PDF"
        if mime_type.startswith("image/"):
            return "IMG"
        if "word" in mime_type or "document" in mime_type:
            return "DOC"
        if "excel" in mime_type or "spreadsheet" in mime_type or "csv" in mime_type:
            return "XLS"
        if "zip" in mime_type or "archive" in mime_type:
            return "ZIP"
        return "FILE"

    @staticmethod
    def _truncate_attachment_name(name):
        if len(name) <= ATTACHMENT_THUMBNAIL_NAME_MAX_CHARS:
            return name
        return name[: ATTACHMENT_THUMBNAIL_NAME_MAX_CHARS - 3] + "..."

    @staticmethod
    def _summarize_preview(text, max_chars=90):
        compact = " ".join((text or "").split())
        if not compact:
            return "No preview available"
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

    def _ensure_detail_message_visible(self):
        if not hasattr(self, "message_stack"):
            return
        if self.message_stack.currentIndex() != 1:
            return
        current_id = (self.current_message or {}).get("id")
        visible_ids = {msg.get("id") for msg in self.filtered_messages if msg.get("id")}
        if not current_id or current_id not in visible_ids:
            self._show_message_list()
            self._clear_detail_view()

    def _clear_detail_view(self, message="No message selected."):
        self.current_message = None
        header_text = "No messages" if "No messages" in message else "Select a message"
        self.message_header.setText(header_text)
        self.email_preview.setHtml(f"<html><body style='font-family:Segoe UI;'>{message}</body></html>")
        self.attachment_list.clear()
        self.cloud_download_list.clear()
        self.cloud_download_label.hide()
        self._update_cloud_download_buttons()
        self.open_cloud_links_btn.setEnabled(False)
        self.cloud_links_info.setText("No linked cloud files found")
        self._render_attachment_thumbnails([])


__all__ = ["EmailListMixin"]
