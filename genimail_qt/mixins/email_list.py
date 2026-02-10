from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import QLabel, QListWidgetItem, QMessageBox, QPushButton, QStyledItemDelegate, QStyle

from genimail.browser.navigation import ensure_light_preview_html, wrap_plain_text_as_html
from genimail.constants import EMAIL_COMPANY_FETCH_PER_FOLDER, EMAIL_LIST_FETCH_TOP, SEARCH_HISTORY_MAX_ITEMS
from genimail.domain.helpers import format_date, format_size, strip_html
from genimail_qt.constants import (
    ATTACHMENT_THUMBNAIL_MAX_INITIAL,
    ATTACHMENT_THUMBNAIL_NAME_MAX_CHARS,
    COMPANY_COLOR_STRIPE_WIDTH,
    EMAIL_LIST_DENSITY_COMFORTABLE,
    EMAIL_LIST_DENSITY_COMPACT,
    EMAIL_LIST_DENSITY_CONFIG_KEY,
    SEARCH_HISTORY_CONFIG_KEY,
)
from genimail_qt.webview_utils import (
    is_inline_attachment,
    normalize_cid_value,
    replace_cid_sources_with_data_urls,
)

# Message list delegate layout constants
_STRIPE_W = 6
_PAD_LEFT = 16
_PAD_RIGHT = 10
_DATE_MIN_W = 54
_GAP = 10

_DENSITY_COMPACT = EMAIL_LIST_DENSITY_COMPACT
_DENSITY_COMFORTABLE = EMAIL_LIST_DENSITY_COMFORTABLE
_ROW_HEIGHT_COMPACT = 42
_ROW_HEIGHT_COMFORTABLE = 64


def _normalize_density_mode(value):
    mode = str(value or "").strip().lower()
    return _DENSITY_COMPACT if mode == _DENSITY_COMPACT else _DENSITY_COMFORTABLE


class CompanyColorDelegate(QStyledItemDelegate):
    """Custom delegate with density-aware rendering for the message list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color_map = {}
        self._is_dark_mode = False
        self._density_mode = _DENSITY_COMFORTABLE

    def set_color_map(self, color_map):
        self._color_map = dict(color_map or {})

    def set_theme_mode(self, mode):
        self._is_dark_mode = str(mode or "").strip().lower() == "dark"

    def set_density_mode(self, mode):
        self._density_mode = _normalize_density_mode(mode)

    @staticmethod
    def _company_color_for_msg(msg, color_map):
        if not color_map:
            return None
        addresses = []
        sender = (msg.get("from", {}).get("emailAddress", {}).get("address") or "").strip().lower()
        if sender:
            addresses.append(sender)
        for field in ("toRecipients", "ccRecipients"):
            for entry in msg.get(field) or []:
                addr = ((entry or {}).get("emailAddress", {}).get("address") or "").strip().lower()
                if addr:
                    addresses.append(addr)
        for address in addresses:
            if "@" not in address:
                continue
            color = color_map.get(address.split("@", 1)[1])
            if color:
                return color
        return None

    def sizeHint(self, option, index):
        _ = index
        row_height = _ROW_HEIGHT_COMPACT if self._density_mode == _DENSITY_COMPACT else _ROW_HEIGHT_COMFORTABLE
        return QSize(max(0, option.rect.width()), row_height)

    @staticmethod
    def _font(base_font, pixel_size, *, bold=False):
        font = QFont(base_font)
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        return font

    @staticmethod
    def _compute_compact_geometry(row_rect, date_text, date_font):
        fm_date = QFontMetrics(date_font)
        date_w = max(_DATE_MIN_W, min(96, fm_date.horizontalAdvance(date_text) + 10))
        date_rect = QRect(row_rect.right() - date_w + 1, row_rect.top(), date_w, row_rect.height())

        sender_w_target = int(row_rect.width() * 0.30)
        sender_w = max(90, min(220, sender_w_target))
        sender_w = max(20, min(sender_w, date_rect.left() - row_rect.left() - _GAP))
        sender_rect = QRect(row_rect.left(), row_rect.top(), sender_w, row_rect.height())

        body_x = sender_rect.right() + 1 + _GAP
        body_w = date_rect.left() - body_x - _GAP
        body_w = max(0, body_w)
        body_rect = QRect(body_x, row_rect.top(), body_w, row_rect.height())
        return date_rect, sender_rect, body_rect, fm_date

    @staticmethod
    def _compute_comfortable_geometry(row_rect, date_text, date_font, preview_text):
        top_pad = 6
        line_gap = 4
        line1_h = 20
        line2_h = max(16, row_rect.height() - top_pad - line_gap - line1_h - 4)
        line1_y = row_rect.top() + top_pad
        line2_y = line1_y + line1_h + line_gap

        fm_date = QFontMetrics(date_font)
        date_w = max(_DATE_MIN_W, min(108, fm_date.horizontalAdvance(date_text) + 10))
        date_rect = QRect(row_rect.right() - date_w + 1, line1_y, date_w, line1_h)
        sender_w = max(20, date_rect.left() - row_rect.left() - _GAP)
        sender_rect = QRect(row_rect.left(), line1_y, sender_w, line1_h)

        line2_left = row_rect.left()
        line2_w = row_rect.width()
        subject_w = line2_w if not preview_text else int(line2_w * 0.48)
        subject_w = max(40, min(subject_w, line2_w))
        subject_rect = QRect(line2_left, line2_y, subject_w, line2_h)
        preview_x = subject_rect.right() + 1 + _GAP
        preview_w = max(0, row_rect.right() - preview_x + 1)
        preview_rect = QRect(preview_x, line2_y, preview_w, line2_h)
        return date_rect, sender_rect, subject_rect, preview_rect, fm_date

    def paint(self, painter, option, index):
        painter.save()
        dark_mode = self._is_dark_mode

        # -- background (selection / alternate) --
        is_selected = bool(option.state & QStyle.State_Selected)
        msg = index.data(Qt.UserRole) or {}
        company_color = self._company_color_for_msg(msg, self._color_map) if isinstance(msg, dict) else None
        selection_color = QColor("#1f2937" if dark_mode else "#dbeafe")
        alternate_color = QColor("#141b24" if dark_mode else "#fbfcfe")

        if is_selected:
            painter.fillRect(option.rect, selection_color)
        elif company_color:
            tint = QColor(company_color)
            tint.setAlpha(28 if dark_mode else 22)
            painter.fillRect(option.rect, tint)
        elif index.row() % 2 == 1:
            painter.fillRect(option.rect, alternate_color)

        # -- color stripe --
        if company_color:
            painter.fillRect(
                QRect(option.rect.left(), option.rect.top(), _STRIPE_W, option.rect.height()),
                QColor(company_color),
            )

        # -- parse payload --
        is_unread = isinstance(msg, dict) and not msg.get("isRead", True)
        fields = index.data(Qt.DisplayRole) or ""
        parts = fields.split("\x1f") if "\x1f" in fields else [fields]
        date_text = parts[0] if len(parts) > 0 else ""
        sender_text = parts[1] if len(parts) > 1 else ""
        subject_text = parts[2] if len(parts) > 2 else ""
        preview_text = parts[3] if len(parts) > 3 else ""
        row_rect = option.rect.adjusted(_STRIPE_W + _PAD_LEFT, 0, -_PAD_RIGHT, 0)
        if row_rect.width() <= 8:
            painter.restore()
            return

        # Unread dot
        if is_unread:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#58a6ff" if dark_mode else "#1f6feb"))
            dot_r = 4
            dot_center_y = row_rect.center().y() if self._density_mode == _DENSITY_COMPACT else row_rect.top() + 14
            painter.drawEllipse(row_rect.left() - 11, dot_center_y - dot_r, dot_r * 2, dot_r * 2)

        base_font = option.font
        sender_color = QColor("#e6edf3" if dark_mode else "#111827")
        date_color = QColor("#9aa4b2" if dark_mode else "#64748b")
        subject_color = QColor("#f0f6fc" if dark_mode else "#0f172a")
        preview_color = QColor("#8b949e" if dark_mode else "#6b7280")

        if self._density_mode == _DENSITY_COMPACT:
            sender_font = self._font(base_font, 13, bold=True)
            date_font = self._font(base_font, 11)
            body_font = self._font(base_font, 12, bold=is_unread)

            date_rect, sender_rect, body_rect, fm_date = self._compute_compact_geometry(row_rect, date_text, date_font)
            body_text = subject_text
            if preview_text and preview_text != "No preview available":
                body_text = f"{subject_text} · {preview_text}"

            painter.setFont(sender_font)
            painter.setPen(sender_color)
            painter.drawText(
                sender_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                QFontMetrics(sender_font).elidedText(sender_text, Qt.ElideRight, sender_rect.width()),
            )
            painter.setFont(date_font)
            painter.setPen(date_color)
            painter.drawText(
                date_rect,
                Qt.AlignRight | Qt.AlignVCenter,
                fm_date.elidedText(date_text, Qt.ElideRight, date_rect.width()),
            )
            if body_rect.width() > 12:
                painter.setFont(body_font)
                painter.setPen(subject_color)
                painter.drawText(
                    body_rect,
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(body_font).elidedText(body_text, Qt.ElideRight, body_rect.width()),
                )
        else:
            sender_font = self._font(base_font, 14, bold=True)
            date_font = self._font(base_font, 11)
            subject_font = self._font(base_font, 13, bold=is_unread)
            preview_font = self._font(base_font, 12)

            date_rect, sender_rect, subject_rect, preview_rect, fm_date = self._compute_comfortable_geometry(
                row_rect, date_text, date_font, preview_text
            )

            painter.setFont(sender_font)
            painter.setPen(sender_color)
            painter.drawText(
                sender_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                QFontMetrics(sender_font).elidedText(sender_text, Qt.ElideRight, sender_rect.width()),
            )
            painter.setFont(date_font)
            painter.setPen(date_color)
            painter.drawText(
                date_rect,
                Qt.AlignRight | Qt.AlignVCenter,
                fm_date.elidedText(date_text, Qt.ElideRight, date_rect.width()),
            )
            painter.setFont(subject_font)
            painter.setPen(subject_color)
            painter.drawText(
                subject_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                QFontMetrics(subject_font).elidedText(subject_text, Qt.ElideRight, subject_rect.width()),
            )
            if preview_rect.width() > 16:
                painter.setFont(preview_font)
                painter.setPen(preview_color)
                painter.drawText(
                    preview_rect,
                    Qt.AlignLeft | Qt.AlignVCenter,
                    QFontMetrics(preview_font).elidedText(preview_text, Qt.ElideRight, preview_rect.width()),
                )

        # Bottom border
        painter.setPen(QPen(QColor("#283242" if dark_mode else "#eef2f7"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        painter.restore()


class EmailListMixin:
    def _set_messages(self, messages, *, track_ids=True):
        """Single entry point for updating the displayed message list.

        All code paths that change the full message list should call this
        instead of writing ``current_messages`` and ``_render_message_list``
        separately.  Keeps ``current_messages``, ``filtered_messages`` and
        ``known_ids`` in sync.
        """
        self.current_messages = list(messages)
        if track_ids:
            self.known_ids = {msg.get("id") for msg in self.current_messages if msg.get("id")}
        self._render_message_list()

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

        # Cache-first: show cached messages instantly before network fetch.
        has_cached = False
        if search_text:
            self._record_search_history(search_text)
        try:
            if search_text:
                cached = self.cache.search_messages(search_text, folder_id=folder_id, limit=EMAIL_LIST_FETCH_TOP)
            else:
                cached = self.cache.get_messages(folder_id, limit=EMAIL_LIST_FETCH_TOP)
            if cached:
                folder_key = self._folder_key_for_id(folder_id)
                enriched = [self._with_folder_meta(msg, folder_id, folder_key) for msg in cached]
                self._set_messages(enriched)
                if self.message_list.count() > 0:
                    self.message_list.setCurrentRow(0)
                has_cached = True
        except Exception:
            pass

        if search_text:
            self._set_status("Refreshing..." if has_cached else "Searching online...")
        else:
            self._set_status("Refreshing..." if has_cached else "Loading messages...")
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
        # Persist results to cache for instant future loads and FTS search.
        if messages:
            try:
                self.cache.save_messages(messages, folder_id)
            except Exception:
                pass
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

        # If user switched to company mode after this worker was submitted,
        # discard the folder results to avoid stomping the company view.
        if self.company_filter_domain:
            return

        folder_key = self._folder_key_for_id(folder_id)
        self.company_result_messages = []
        self._company_search_override = None
        enriched = [self._with_folder_meta(msg, folder_id, folder_key) for msg in messages]
        self._set_messages(enriched)
        self._refresh_company_sidebar()
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
    # Search history
    # ------------------------------------------------------------------

    def _load_search_history(self):
        if not hasattr(self, "config"):
            return
        history = self.config.get(SEARCH_HISTORY_CONFIG_KEY, []) or []
        if not isinstance(history, list):
            history = [history]
        seen = set()
        deduped = []
        for term in history:
            if not isinstance(term, str):
                continue
            key = term.strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(term.strip())
        if hasattr(self, "_search_completer"):
            self._search_completer.model().setStringList(deduped)

    def _record_search_history(self, search_text):
        term = (search_text or "").strip()
        if not term or not hasattr(self, "config"):
            return
        history = self.config.get(SEARCH_HISTORY_CONFIG_KEY, []) or []
        if not isinstance(history, list):
            history = [history]
        # Deduplicate case-insensitively, keeping the newest casing
        deduped = [term]
        seen = {term.lower()}
        for existing in history:
            if not isinstance(existing, str):
                continue
            key = existing.strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(existing.strip())
        deduped = deduped[:SEARCH_HISTORY_MAX_ITEMS]
        self.config.set(SEARCH_HISTORY_CONFIG_KEY, deduped)
        self._load_search_history()

    # ------------------------------------------------------------------
    # List density
    # ------------------------------------------------------------------

    def _get_email_list_density_mode(self):
        mode = getattr(self, "_email_list_density", None)
        if mode is not None:
            return _normalize_density_mode(mode)
        raw = _DENSITY_COMFORTABLE
        if hasattr(self, "config"):
            raw = self.config.get(EMAIL_LIST_DENSITY_CONFIG_KEY, _DENSITY_COMFORTABLE)
        mode = _normalize_density_mode(raw)
        self._email_list_density = mode
        return mode

    def _set_email_list_density_mode(self, mode, persist=False):
        normalized = _normalize_density_mode(mode)
        self._email_list_density = normalized
        if hasattr(self, "_company_color_delegate"):
            self._company_color_delegate.set_density_mode(normalized)
        if hasattr(self, "message_list"):
            self.message_list.doItemsLayout()
            self.message_list.viewport().update()
        self._sync_email_density_buttons()
        if persist and hasattr(self, "config"):
            self.config.set(EMAIL_LIST_DENSITY_CONFIG_KEY, normalized)

    def _sync_email_density_buttons(self):
        if not hasattr(self, "email_density_compact_btn") or not hasattr(self, "email_density_comfortable_btn"):
            return
        mode = self._get_email_list_density_mode()
        self.email_density_compact_btn.blockSignals(True)
        self.email_density_compact_btn.setChecked(mode == _DENSITY_COMPACT)
        self.email_density_compact_btn.blockSignals(False)
        self.email_density_comfortable_btn.blockSignals(True)
        self.email_density_comfortable_btn.setChecked(mode == _DENSITY_COMFORTABLE)
        self.email_density_comfortable_btn.blockSignals(False)

    def _on_email_density_button_clicked(self, mode):
        self._set_email_list_density_mode(mode, persist=True)

    # ------------------------------------------------------------------
    # Message list rendering
    # ------------------------------------------------------------------

    def _render_message_list(self):
        self.filtered_messages = list(self.current_messages)
        self.message_list.clear()
        self._ensure_company_color_delegate()
        for msg in self.filtered_messages:
            sender = msg.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
            subject = msg.get("subject") or "(No subject)"
            received = format_date(msg.get("receivedDateTime", ""))
            preview = self._summarize_preview(msg.get("bodyPreview", ""), max_chars=200)
            # Fields separated by \x1f (unit separator) for the delegate to parse
            line = f"{received}\x1f{sender}\x1f{subject}\x1f{preview}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, msg)
            self.message_list.addItem(item)

    def _ensure_company_color_delegate(self):
        if not hasattr(self, "_company_color_delegate"):
            self._company_color_delegate = CompanyColorDelegate(self.message_list)
            self.message_list.setItemDelegate(self._company_color_delegate)
        color_map = getattr(self, "_company_color_map", {})
        self._company_color_delegate.set_color_map(color_map)
        self._company_color_delegate.set_theme_mode(getattr(self, "_theme_mode", "light"))
        self._company_color_delegate.set_density_mode(self._get_email_list_density_mode())

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
        self.cache.save_message_body(message_id, body.get("contentType", ""), body.get("content", ""))
        self.cache.save_attachments(message_id, attachments)
        return {"id": message_id, "detail": detail, "attachments": attachments}

    def _on_message_detail_loaded(self, payload):
        message_id = payload.get("id")
        detail = payload.get("detail") or {}
        attachments = payload.get("attachments") or []
        if message_id:
            self.message_cache[message_id] = detail
            self.attachment_cache[message_id] = attachments
        if message_id and message_id != (self.current_message or {}).get("id"):
            return
        self._render_message_detail(detail, attachments)

    def _render_message_detail(self, detail, attachments):
        if hasattr(self, "_clear_download_results"):
            self._clear_download_results()
        sender = detail.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
        address = detail.get("from", {}).get("emailAddress", {}).get("address") or ""
        received = format_date(detail.get("receivedDateTime", ""))
        subject = detail.get("subject") or "(No subject)"
        self.message_header.setText(f"{subject}\nFrom: {sender} <{address}> · {received}")

        company_color = self._company_color_for_message(detail) if hasattr(self, "_company_color_for_message") else None
        if company_color:
            self.message_header.setStyleSheet(
                f"border-left: {COMPANY_COLOR_STRIPE_WIDTH}px solid {company_color}; padding-left: 10px;"
            )
        else:
            self.message_header.setStyleSheet("")

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
        self._render_attachment_thumbnails([])
        if hasattr(self, "_clear_download_results"):
            self._clear_download_results()


__all__ = ["EmailListMixin"]
