from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton

from genimail.constants import FOLDER_DISPLAY
from genimail.domain.helpers import normalize_company_query
from genimail_qt.company_tab_manager_dialog import CompanyTabManagerDialog


class CompanyMixin:
    FOLDER_ORDER = ("inbox", "sentitems", "junkemail", "deleteditems", "drafts", "colorx")
    FOLDER_LABELS = {
        "all": "All",
        "inbox": "Inbox",
        "sentitems": "Sent",
        "junkemail": "Junk",
        "deleteditems": "Deleted",
        "drafts": "Drafts",
        "colorx": "color x",
    }

    def _reset_company_state(self, clear_cache=False):
        self.company_filter_domain = None
        self.company_result_messages = []
        self.company_folder_filter = "all"
        self._company_search_override = None
        if clear_cache:
            self.company_query_cache.clear()
            self.company_query_inflight.clear()
        self._sync_company_tab_checks()
        self._sync_company_folder_filter_checks()
        self._set_company_folder_filter_visible(False)
        self._update_company_filter_badge()

    @staticmethod
    def _normalize_folder_key(name):
        return "".join(ch for ch in (name or "").strip().lower() if ch.isalnum())

    @classmethod
    def _folder_key_from_folder(cls, folder):
        well_known = cls._normalize_folder_key((folder or {}).get("wellKnownName"))
        if well_known in cls.FOLDER_ORDER:
            return well_known

        display_name = cls._normalize_folder_key((folder or {}).get("displayName"))
        alias_map = {
            "inbox": "inbox",
            "sent": "sentitems",
            "sentitems": "sentitems",
            "sentmail": "sentitems",
            "junk": "junkemail",
            "junkemail": "junkemail",
            "deleted": "deleteditems",
            "deleteditems": "deleteditems",
            "trash": "deleteditems",
            "draft": "drafts",
            "drafts": "drafts",
            "colorx": "colorx",
        }
        if display_name in alias_map:
            return alias_map[display_name]
        if display_name in cls.FOLDER_ORDER:
            return display_name
        return ""

    def _populate_folders(self, folders):
        if not hasattr(self, "folder_buttons_layout"):
            return

        while self.folder_buttons_layout.count():
            item = self.folder_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible_folders = []
        for folder in folders or []:
            key = self._folder_key_from_folder(folder)
            if key:
                visible_folders.append((key, folder))

        # Ensure core folders are always available even if Graph list output varies.
        existing_keys = {key for key, _ in visible_folders}
        for key in ("inbox", "sentitems", "junkemail", "deleteditems", "drafts"):
            if key not in existing_keys:
                visible_folders.append(
                    (
                        key,
                        {
                            "id": key,
                            "displayName": self.FOLDER_LABELS.get(key, key),
                            "wellKnownName": key,
                        },
                    )
                )

        rank = {key: idx for idx, key in enumerate(self.FOLDER_ORDER)}
        visible_folders.sort(key=lambda item: (rank.get(item[0], 999), (item[1].get("displayName") or "").lower()))

        self.company_folder_sources = []
        self.folder_buttons = []
        selected_button = None
        selected_folder = None

        for key, folder in visible_folders:
            folder_name = folder.get("displayName", "")
            display_name = self.FOLDER_LABELS.get(key) or FOLDER_DISPLAY.get(folder_name.lower(), folder_name)
            btn = QPushButton(display_name)
            btn.setObjectName("folderButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, f=folder, b=btn: self._on_folder_button_clicked(f, b))
            self.folder_buttons_layout.addWidget(btn)
            self.folder_buttons.append((btn, folder))
            self.company_folder_sources.append(
                {
                    "id": folder.get("id") or key,
                    "key": key,
                    "label": self.FOLDER_LABELS.get(key, display_name),
                }
            )

            if key == "inbox":
                selected_button = btn
                selected_folder = folder

        self.folder_buttons_layout.addStretch(1)
        self._rebuild_company_folder_filter_chips()

        if selected_button is None and self.folder_buttons:
            selected_button, selected_folder = self.folder_buttons[0]
        if selected_button is not None and selected_folder is not None:
            self._on_folder_button_clicked(selected_folder, selected_button)

    def _on_folder_button_clicked(self, folder, selected_button):
        for btn, _folder in getattr(self, "folder_buttons", []):
            btn.blockSignals(True)
            btn.setChecked(btn is selected_button)
            btn.blockSignals(False)

        if self.company_filter_domain:
            self._reset_company_state()

        self._show_message_list()
        self._clear_detail_view()
        self.current_folder_id = (folder or {}).get("id") or "inbox"
        self._load_messages()

    def _refresh_company_sidebar(self):
        self.company_domain_labels = {}
        self._company_color_map = {}
        entries = self._load_company_queries()
        self.company_entries_visible = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            domain = self._normalize_company_query(entry.get("domain", ""))
            if not domain:
                continue
            label = (entry.get("label") or "").strip() or domain
            color = (entry.get("color") or "").strip() or None
            self.company_domain_labels[domain] = label
            if color:
                self._company_color_map[domain] = color
            self.company_entries_visible.append({"domain": domain, "label": label, "color": color})

        if self.company_filter_domain and self.company_filter_domain not in {entry["domain"] for entry in self.company_entries_visible}:
            self._reset_company_state()

        self._rebuild_company_tabs()
        self._rebuild_company_folder_filter_chips()
        self._sync_company_tab_checks()
        self._sync_company_folder_filter_checks()
        self._set_company_folder_filter_visible(bool(self.company_filter_domain))
        self._update_company_filter_badge()

    def _rebuild_company_tabs(self):
        if not hasattr(self, "company_tabs_layout"):
            return

        while self.company_tabs_layout.count():
            item = self.company_tabs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.company_tab_buttons = {}
        all_btn = QPushButton("All Companies")
        all_btn.setObjectName("companyTabButton")
        all_btn.setCheckable(True)
        all_btn.clicked.connect(lambda _checked=False: self._on_company_tab_clicked(None))
        self.company_tabs_layout.addWidget(all_btn)
        self.company_tab_buttons[None] = all_btn

        for entry in self.company_entries_visible:
            btn = QPushButton(entry["label"])
            btn.setObjectName("companyTabButton")
            btn.setCheckable(True)
            color = (entry.get("color") or "").strip()
            if color:
                base = QColor(color)
                btn.setStyleSheet(
                    f"QPushButton#companyTabButton {{"
                    f" background: {base.lighter(180).name()}; border: 2px solid {color};"
                    f" color: #1b1f24; font-weight: 600;"
                    f"}}"
                    f"QPushButton#companyTabButton:hover {{"
                    f" background: {base.lighter(155).name()}; border-color: {color};"
                    f"}}"
                    f"QPushButton#companyTabButton:checked {{"
                    f" background: {color}; border-color: {color}; color: #ffffff;"
                    f"}}"
                )
            btn.clicked.connect(lambda _checked=False, domain=entry["domain"]: self._on_company_tab_clicked(domain))
            self.company_tabs_layout.addWidget(btn)
            self.company_tab_buttons[entry["domain"]] = btn

        self.company_tabs_layout.addStretch(1)

    def _rebuild_company_folder_filter_chips(self):
        if not hasattr(self, "company_folder_filter_layout"):
            return

        while self.company_folder_filter_layout.count():
            item = self.company_folder_filter_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.company_folder_filter_buttons = {}
        ordered_keys = ["all", *[item["key"] for item in self.company_folder_sources if item.get("key") in self.FOLDER_ORDER]]
        seen = set()
        for key in ordered_keys:
            if key in seen:
                continue
            seen.add(key)
            label = self.FOLDER_LABELS.get(key, key)
            btn = QPushButton(label)
            btn.setObjectName("companyFolderChip")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, k=key: self._set_company_folder_filter(k))
            self.company_folder_filter_layout.addWidget(btn)
            self.company_folder_filter_buttons[key] = btn

        self.company_folder_filter_layout.addStretch(1)

    def _sync_company_tab_checks(self):
        selected = (self.company_filter_domain or "").strip().lower() or None
        for domain, btn in getattr(self, "company_tab_buttons", {}).items():
            btn.blockSignals(True)
            btn.setChecked(domain == selected if domain else selected is None)
            btn.blockSignals(False)

    def _sync_company_folder_filter_checks(self):
        selected = (self.company_folder_filter or "all").strip().lower() or "all"
        for key, btn in getattr(self, "company_folder_filter_buttons", {}).items():
            btn.blockSignals(True)
            btn.setChecked(key == selected)
            btn.blockSignals(False)

    def _set_company_folder_filter_visible(self, visible):
        if hasattr(self, "company_folder_filter_widget"):
            self.company_folder_filter_widget.setVisible(bool(visible))

    def _set_company_folder_filter(self, key):
        normalized = (key or "all").strip().lower()
        if normalized not in self.company_folder_filter_buttons:
            normalized = "all"
        if self.company_folder_filter == normalized:
            return
        self.company_folder_filter = normalized
        self._sync_company_folder_filter_checks()
        self._update_company_filter_badge()
        if self.company_filter_domain:
            self._apply_company_folder_filter()

    def _on_company_tab_clicked(self, domain):
        domain = (domain or "").strip().lower() or None
        if domain == self.company_filter_domain:
            domain = None

        if not domain:
            self._reset_company_state()
            self._load_messages()
            return

        self.company_filter_domain = domain
        if not self.company_folder_filter:
            self.company_folder_filter = "all"
        self._sync_company_tab_checks()
        self._sync_company_folder_filter_checks()
        self._set_company_folder_filter_visible(True)
        self._update_company_filter_badge()
        self._show_message_list()
        self._set_status(f"Loading messages for {domain} across folders...")
        self._load_company_messages_all_folders(domain)

    def _set_company_tabs_enabled(self, enabled):
        """Enable/disable company tab buttons during loading."""
        for btn in getattr(self, "company_tab_buttons", {}).values():
            if btn is not None:
                btn.setEnabled(enabled)

    def _update_company_filter_badge(self):
        if not hasattr(self, "company_filter_badge"):
            return

        query = (self.company_filter_domain or "").strip().lower()
        if not query:
            self.company_filter_badge.hide()
            if hasattr(self, "clear_company_filter_btn"):
                self.clear_company_filter_btn.hide()
            return

        display_label = (self.company_domain_labels.get(query) or "").strip()
        if display_label and display_label.lower() != query:
            company_text = f"{display_label} ({query})"
        else:
            company_text = query

        folder_key = (self.company_folder_filter or "all").strip().lower() or "all"
        folder_label = self.FOLDER_LABELS.get(folder_key, folder_key)
        if folder_key == "all":
            self.company_filter_badge.setText(f"Company: {company_text} · Folder: All")
        else:
            self.company_filter_badge.setText(f"Company: {company_text} · Folder: {folder_label}")
        self.company_filter_badge.show()
        if hasattr(self, "clear_company_filter_btn"):
            self.clear_company_filter_btn.show()

    def _clear_company_filter(self, force_reload=False):
        had_filter = bool(self.company_filter_domain)
        if not had_filter and not force_reload:
            return
        self._reset_company_state()
        self._load_messages()

    def _open_company_manager(self):
        existing_entries = self._load_company_queries()
        all_domains = []
        if hasattr(self, "cache") and hasattr(self.cache, "get_all_domains"):
            try:
                for item in self.cache.get_all_domains() or []:
                    if isinstance(item, dict):
                        domain = self._normalize_company_query(item.get("domain", ""))
                    else:
                        domain = self._normalize_company_query(item)
                    if domain and domain not in all_domains:
                        all_domains.append(domain)
            except Exception:
                all_domains = []

        dialog = CompanyTabManagerDialog(self, existing_entries, all_domains=all_domains)
        dialog.exec()
        if not dialog.changed:
            return

        previous_active = (self.company_filter_domain or "").strip().lower() or None
        self._save_company_queries(dialog.entries)
        self._refresh_company_sidebar()
        visible_domains = {entry.get("domain") for entry in dialog.entries if isinstance(entry, dict)}
        if previous_active and previous_active in visible_domains:
            self.company_filter_domain = previous_active
            self._sync_company_tab_checks()
            self._set_company_folder_filter_visible(True)
            self._update_company_filter_badge()
            if not self.company_result_messages:
                self._load_company_messages_all_folders(previous_active)
            return
        if previous_active and previous_active not in visible_domains:
            self._clear_company_filter(force_reload=True)

    @staticmethod
    def _normalize_company_query(value):
        return normalize_company_query(value)

    def _load_company_queries(self):
        raw = self.config.get("companies", {}) or {}
        entries = []
        seen_domains = set()

        def add_entry(domain, label="", color=None):
            normalized = CompanyMixin._normalize_company_query(domain)
            if not normalized or normalized in seen_domains:
                return
            seen_domains.add(normalized)
            entries.append({"domain": normalized, "label": (label or "").strip(), "color": color or None})

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    add_entry(item, "")
                    continue
                if isinstance(item, dict):
                    add_entry(item.get("domain", ""), item.get("label", ""), item.get("color"))
        elif isinstance(raw, dict):
            for key in raw.keys():
                add_entry(key, "")

        return entries

    def _save_company_queries(self, queries):
        normalized = []
        seen_domains = set()
        for value in queries or []:
            if isinstance(value, dict):
                domain = CompanyMixin._normalize_company_query(value.get("domain", ""))
                label = (value.get("label") or "").strip()
                color = (value.get("color") or "").strip() or None
            else:
                domain = CompanyMixin._normalize_company_query(value)
                label = ""
                color = None
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            entry = {"domain": domain, "label": label}
            if color:
                entry["color"] = color
            normalized.append(entry)
        self.config.set("companies", normalized)

    def _get_company_domain_set(self, key):
        values = self.config.get(key, [])
        if not isinstance(values, list):
            return set()
        normalized = set()
        for value in values:
            if not isinstance(value, str):
                continue
            domain = value.strip().lower()
            if domain:
                normalized.add(domain)
        return normalized

    def _save_company_domain_set(self, key, domains):
        ordered = sorted({(domain or "").strip().lower() for domain in domains if (domain or "").strip()})
        self.config.set(key, ordered)

    @staticmethod
    def _parse_company_query(query):
        normalized = (query or "").strip().lower()
        if not normalized:
            return "text", ""
        if "@" in normalized and " " not in normalized:
            return "email", normalized
        if "." in normalized and "@" not in normalized and " " not in normalized:
            return "domain", normalized
        return "text", normalized

    def _count_messages_for_query(self, query):
        source = self.company_result_messages if self.company_result_messages else self.current_messages
        return sum(1 for msg in source if self._message_matches_company_filter(msg, query))

    @classmethod
    def _message_matches_company_filter(cls, msg, query):
        kind, value = cls._parse_company_query(query)
        if not value:
            return True
        participants = []

        sender = msg.get("from", {}).get("emailAddress", {})
        participants.append(
            (
                (sender.get("address") or "").strip().lower(),
                (sender.get("name") or "").strip().lower(),
            )
        )

        for field in ("toRecipients", "ccRecipients"):
            for entry in msg.get(field) or []:
                email = (entry or {}).get("emailAddress", {})
                participants.append(
                    (
                        (email.get("address") or "").strip().lower(),
                        (email.get("name") or "").strip().lower(),
                    )
                )

        addresses = [address for address, _name in participants if address]
        names = [name for _address, name in participants if name]

        if kind == "email":
            return any(address == value for address in addresses)
        if kind == "domain":
            for address in addresses:
                if "@" not in address:
                    continue
                if address.split("@", 1)[1] == value:
                    return True
            return False
        return any(value in address for address in addresses) or any(value in name for name in names)

    def _company_color_for_message(self, msg):
        """Return the company color hex for a message, or None."""
        color_map = getattr(self, "_company_color_map", {})
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

    def _check_detail_message_visibility(self):
        self._ensure_detail_message_visible()


__all__ = ["CompanyMixin"]
