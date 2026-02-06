import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidgetItem, QMessageBox, QPushButton

from genimail.browser.navigation import ensure_light_preview_html, wrap_plain_text_as_html
from genimail.constants import (
    CLOUD_PDF_SOURCE_SUMMARY_MAX,
    EMAIL_COMPANY_CACHE_TTL_SEC,
    EMAIL_COMPANY_FETCH_PER_FOLDER,
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

    def _load_company_messages_all_folders(self, company_query):
        if not self.graph:
            return
        query_key = (company_query or "").strip().lower()
        if not query_key:
            return

        self._company_search_override = None
        cache_messages = EmailListMixin._load_company_messages_from_cache(self, query_key)
        showing_cache = bool(cache_messages)
        if showing_cache:
            self.company_result_messages = cache_messages
            self.company_folder_filter = self.company_folder_filter or "all"
            self._apply_company_folder_filter()
            self._set_status(f'Loaded {len(self.filtered_messages)} cached message(s) for "{query_key}".')

        cached = self.company_query_cache.get(query_key)
        now = time.time()
        if cached and not showing_cache:
            cached_messages = list(cached.get("messages") or [])
            self.company_result_messages = cached_messages
            self.company_folder_filter = self.company_folder_filter or "all"
            self._apply_company_folder_filter()

            cache_age = now - float(cached.get("fetched_at") or 0)
            if cache_age <= EMAIL_COMPANY_CACHE_TTL_SEC:
                self._set_status(
                    f'Loaded {len(self.filtered_messages)} cached message(s) for "{query_key}".'
                )
                return
            self._set_status(f"Refreshing {query_key} across folders...")
        elif cached and showing_cache:
            cache_age = now - float(cached.get("fetched_at") or 0)
            if cache_age <= EMAIL_COMPANY_CACHE_TTL_SEC:
                return
            self._set_status(f"Refreshing {query_key} across folders...")
        elif showing_cache:
            self._set_status(f"Refreshing {query_key} across folders...")
        else:
            self._set_status(f"Loading {query_key} across folders...")

        if query_key in self.company_query_inflight:
            return

        self.company_query_inflight.add(query_key)
        self._company_load_token = getattr(self, "_company_load_token", 0) + 1
        load_token = self._company_load_token
        if not cached and not showing_cache:
            self._show_message_list()
            self.current_messages = []
            self.filtered_messages = []
            self.message_list.clear()
            self._clear_detail_view(f'Loading messages for "{query_key}"...')
        self.workers.submit(
            lambda q=query_key, token=load_token: self._company_messages_worker(q, token),
            self._on_company_messages_loaded,
            lambda trace_text, q=query_key: self._on_company_messages_error(q, trace_text),
        )

    def _company_messages_worker(self, company_query, token=None):
        deduped = {}
        errors = []
        sources = list(self.company_folder_sources or [])
        if not sources:
            sources = [{"id": self.current_folder_id, "key": self._folder_key_for_id(self.current_folder_id), "label": "Current"}]

        search_hint, filter_hint = self._company_query_hints(company_query)

        for source in sources:
            folder_id = source.get("id")
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            try:
                page, _ = self.graph.get_messages(
                    folder_id=folder_id,
                    top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    search=search_hint,
                    filter_str=filter_hint,
                )
            except Exception:
                try:
                    page, _ = self.graph.get_messages(
                        folder_id=folder_id,
                        top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    )
                except Exception as exc:
                    errors.append(f"{folder_label}: {exc}")
                    continue

            if page and hasattr(self, "cache") and hasattr(self.cache, "save_messages"):
                try:
                    self.cache.save_messages(page, folder_id)
                except Exception as exc:
                    print(f"[CACHE] unable to save company page for {folder_label}: {exc}")

            try:
                for msg in page or []:
                    msg_with_folder = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
                    if not self._message_matches_company_filter(msg_with_folder, company_query):
                        continue
                    msg_id = msg_with_folder.get("id")
                    if not msg_id:
                        continue
                    existing = deduped.get(msg_id)
                    if existing is None or msg_with_folder.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                        deduped[msg_id] = msg_with_folder
            except Exception as exc:
                errors.append(f"{folder_label}: {exc}")

        messages = sorted(deduped.values(), key=lambda msg: msg.get("receivedDateTime", ""), reverse=True)
        return {"query": company_query, "messages": messages, "errors": errors, "fetched_at": time.time(), "token": token}

    def _load_company_messages_from_cache(self, company_query, search_text=None):
        if not hasattr(self, "cache") or not hasattr(self.cache, "search_company_messages"):
            return []
        try:
            cached_rows = self.cache.search_company_messages(company_query, search_text=search_text) or []
        except Exception as exc:
            print(f"[CACHE] company query failed for {company_query}: {exc}")
            return []

        sources_by_id = {
            (source.get("id") or "").strip().lower(): source
            for source in (self.company_folder_sources or [])
            if (source.get("id") or "").strip()
        }
        deduped = {}
        for msg in cached_rows:
            if not self._message_matches_company_filter(msg, company_query):
                continue
            folder_id = (msg.get("_folder_id") or "").strip() or self.current_folder_id
            source = sources_by_id.get(folder_id.strip().lower()) or {}
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            enriched = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
            msg_id = enriched.get("id")
            if not msg_id:
                continue
            existing = deduped.get(msg_id)
            if existing is None or enriched.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                deduped[msg_id] = enriched

        return sorted(deduped.values(), key=lambda item: item.get("receivedDateTime", ""), reverse=True)

    def _load_company_messages_with_search(self, company_query, search_text):
        query_key = (company_query or "").strip().lower()
        search_key = (search_text or "").strip().lower()
        if not query_key:
            return
        if not search_key:
            self._apply_company_folder_filter()
            return

        self._company_search_override = None
        if not self.company_result_messages:
            cache_messages = EmailListMixin._load_company_messages_from_cache(self, query_key, search_key)
            if cache_messages:
                self.company_result_messages = cache_messages

        self.company_folder_filter = self.company_folder_filter or "all"
        self._show_message_list()
        self._apply_company_folder_filter()
        local_count = len(self.filtered_messages)

        if not self.graph:
            self._set_status(f'Found {local_count} local message(s) for "{query_key}".')
            return

        self._company_load_token = getattr(self, "_company_load_token", 0) + 1
        load_token = self._company_load_token
        if local_count:
            self._set_status(f'Found {local_count} local message(s). Refining "{query_key}" search...')
        else:
            self._set_status(f'Searching "{search_key}" in "{query_key}"...')
        self.workers.submit(
            lambda q=query_key, text=search_key, token=load_token: self._company_search_worker(q, text, token),
            self._on_company_search_loaded,
            lambda trace_text, q=query_key, text=search_key, token=load_token: self._on_company_search_error(
                q, text, token, trace_text
            ),
        )

    def _company_search_worker(self, company_query, search_text, token):
        deduped = {}
        errors = []
        sources = list(self.company_folder_sources or [])
        if not sources:
            sources = [{"id": self.current_folder_id, "key": self._folder_key_for_id(self.current_folder_id), "label": "Current"}]

        combined_search = f"{company_query} {search_text}".strip()
        for source in sources:
            folder_id = source.get("id")
            folder_key = source.get("key") or self._folder_key_for_id(folder_id)
            folder_label = source.get("label") or folder_key
            try:
                page, _ = self.graph.get_messages(
                    folder_id=folder_id,
                    top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    search=combined_search,
                )
            except Exception:
                try:
                    page, _ = self.graph.get_messages(
                        folder_id=folder_id,
                        top=EMAIL_COMPANY_FETCH_PER_FOLDER,
                    )
                except Exception as exc:
                    errors.append(f"{folder_label}: {exc}")
                    continue

            if page and hasattr(self, "cache") and hasattr(self.cache, "save_messages"):
                try:
                    self.cache.save_messages(page, folder_id)
                except Exception as exc:
                    print(f"[CACHE] unable to save company search page for {folder_label}: {exc}")

            try:
                for msg in page or []:
                    msg_with_folder = self._with_folder_meta(msg, folder_id, folder_key, folder_label)
                    if not self._message_matches_company_filter(msg_with_folder, company_query):
                        continue
                    if not self._message_matches_search(msg_with_folder, search_text):
                        continue
                    msg_id = msg_with_folder.get("id")
                    if not msg_id:
                        continue
                    existing = deduped.get(msg_id)
                    if existing is None or msg_with_folder.get("receivedDateTime", "") > existing.get("receivedDateTime", ""):
                        deduped[msg_id] = msg_with_folder
            except Exception as exc:
                errors.append(f"{folder_label}: {exc}")

        messages = sorted(deduped.values(), key=lambda msg: msg.get("receivedDateTime", ""), reverse=True)
        return {
            "query": company_query,
            "search_text": search_text,
            "messages": messages,
            "errors": errors,
            "fetched_at": time.time(),
            "token": token,
        }

    def _on_company_search_loaded(self, payload):
        token = payload.get("token")
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return

        query = (payload.get("query") or "").strip().lower()
        if query != (self.company_filter_domain or "").strip().lower():
            return

        payload_search = (payload.get("search_text") or "").strip().lower()
        current_search = (self.search_input.text() or "").strip().lower()
        if not current_search:
            self._company_search_override = None
            self._apply_company_folder_filter()
            return
        if payload_search != current_search:
            return

        self._company_search_override = {
            "query": query,
            "search_text": payload_search,
            "messages": list(payload.get("messages") or []),
            "fetched_at": float(payload.get("fetched_at") or time.time()),
        }
        self._apply_company_folder_filter()
        self._ensure_detail_message_visible()

        errors = payload.get("errors") or []
        if errors:
            self._set_status(
                f'Found {len(self.filtered_messages)} message(s) for "{query}" with partial folder search errors.'
            )
        else:
            self._set_status(f'Found {len(self.filtered_messages)} message(s) for "{query}" matching "{payload_search}".')

    def _on_company_search_error(self, query, search_text, token, trace_text):
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return
        if (query or "").strip().lower() != (self.company_filter_domain or "").strip().lower():
            return
        if (search_text or "").strip().lower() != (self.search_input.text() or "").strip().lower():
            return

        self._company_search_override = None
        self._set_status(f'Search unavailable right now. Showing locally filtered results for "{query}".')
        print(trace_text)

    def _on_company_messages_loaded(self, payload):
        query = (payload.get("query") or "").strip().lower()
        self.company_query_inflight.discard(query)
        self.company_query_cache[query] = {
            "messages": list(payload.get("messages") or []),
            "errors": list(payload.get("errors") or []),
            "fetched_at": float(payload.get("fetched_at") or time.time()),
        }

        token = payload.get("token")
        current_token = getattr(self, "_company_load_token", None)
        if token is not None and current_token is not None and token != current_token:
            return

        if query != (self.company_filter_domain or "").strip().lower():
            return

        self.company_result_messages = payload.get("messages") or []
        self._company_search_override = None
        self.company_folder_filter = self.company_folder_filter or "all"
        self._apply_company_folder_filter()

        errors = payload.get("errors") or []
        if errors:
            self._set_status(
                f'Loaded {len(self.filtered_messages)} message(s) for "{query}" with partial folder errors.'
            )
        else:
            self._set_status(f'Loaded {len(self.filtered_messages)} message(s) for "{query}" across folders.')

    def _on_company_messages_error(self, query, trace_text):
        self.company_query_inflight.discard((query or "").strip().lower())
        if (query or "").strip().lower() != (self.company_filter_domain or "").strip().lower():
            return
        self._set_status(f'Unable to refresh "{query}" right now.')
        print(trace_text)

    def _company_query_hints(self, query):
        if hasattr(self, "_parse_company_query"):
            kind, value = self._parse_company_query(query)
        else:
            kind, value = ("text", (query or "").strip().lower())
        if not value:
            return None, None
        if kind == "email":
            safe_value = value.replace("'", "''")
            return None, f"from/emailAddress/address eq '{safe_value}'"
        return value, None

    def _apply_company_folder_filter(self):
        search_text = (self.search_input.text() or "").strip().lower()
        source_messages = list(self.company_result_messages or [])
        if search_text:
            override = getattr(self, "_company_search_override", None) or {}
            if (
                (override.get("query") or "").strip().lower() == (self.company_filter_domain or "").strip().lower()
                and (override.get("search_text") or "").strip().lower() == search_text
            ):
                source_messages = list(override.get("messages") or [])
        else:
            self._company_search_override = None

        folder_filter = (self.company_folder_filter or "all").strip().lower() or "all"
        if folder_filter != "all":
            source_messages = [msg for msg in source_messages if (msg.get("_folder_key") or "").strip().lower() == folder_filter]

        if search_text:
            source_messages = [msg for msg in source_messages if self._message_matches_search(msg, search_text)]

        self.current_messages = source_messages
        self.known_ids = {msg.get("id") for msg in self.current_messages if msg.get("id")}
        self._render_message_list()
        if self.message_list.count() > 0:
            self.message_list.setCurrentRow(0)
            self._show_message_list()
        else:
            self._show_message_list()
            self._clear_detail_view("No messages match this company filter.")
        self._ensure_detail_message_visible()

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
