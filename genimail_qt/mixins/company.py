from PySide6.QtWidgets import QPushButton

from genimail.constants import FOLDER_DISPLAY
from genimail_qt.company_tab_manager_dialog import CompanyTabManagerDialog, normalize_company_query


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
            self.company_filter_domain = None
            self.company_result_messages = []
            self.company_folder_filter = "all"
            self._sync_company_tab_checks()
            self._sync_company_folder_filter_checks()
            self._set_company_folder_filter_visible(False)
            self._update_company_filter_badge()

        self._show_message_list()
        self._clear_detail_view()
        self.current_folder_id = (folder or {}).get("id") or "inbox"
        self._load_messages()

    def _refresh_company_sidebar(self):
        self.company_domain_labels = {}
        queries = self._load_company_queries()
        self.company_entries_visible = []
        for query in queries:
            self.company_domain_labels[query] = query
            self.company_entries_visible.append({"domain": query, "label": query})

        if self.company_filter_domain and self.company_filter_domain not in {entry["domain"] for entry in self.company_entries_visible}:
            self.company_filter_domain = None
            self.company_result_messages = []
            self.company_folder_filter = "all"

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
        if self.company_filter_domain and hasattr(self, "_apply_company_folder_filter"):
            self._apply_company_folder_filter()

    def _on_company_tab_clicked(self, domain):
        domain = (domain or "").strip().lower() or None
        if domain == self.company_filter_domain:
            domain = None

        if not domain:
            self.company_filter_domain = None
            self.company_result_messages = []
            self.company_folder_filter = "all"
            self._sync_company_tab_checks()
            self._sync_company_folder_filter_checks()
            self._set_company_folder_filter_visible(False)
            self._update_company_filter_badge()
            self._load_messages()
            return

        self.company_filter_domain = domain
        self.company_folder_filter = "all"
        self._sync_company_tab_checks()
        self._sync_company_folder_filter_checks()
        self._set_company_folder_filter_visible(True)
        self._update_company_filter_badge()
        self._show_message_list()
        self._set_status(f"Loading messages for {domain} across folders...")
        if hasattr(self, "_load_company_messages_all_folders"):
            self._load_company_messages_all_folders(domain)

    def _update_company_filter_badge(self):
        if not hasattr(self, "company_filter_badge"):
            return

        query = (self.company_filter_domain or "").strip().lower()
        if not query:
            self.company_filter_badge.hide()
            if hasattr(self, "clear_company_filter_btn"):
                self.clear_company_filter_btn.hide()
            return

        folder_key = (self.company_folder_filter or "all").strip().lower() or "all"
        folder_label = self.FOLDER_LABELS.get(folder_key, folder_key)
        if folder_key == "all":
            self.company_filter_badge.setText(f'Company: "{query}" · Folder: All')
        else:
            self.company_filter_badge.setText(f'Company: "{query}" · Folder: {folder_label}')
        self.company_filter_badge.show()
        if hasattr(self, "clear_company_filter_btn"):
            self.clear_company_filter_btn.show()

    def _clear_company_filter(self, force_reload=False):
        had_filter = bool(self.company_filter_domain)
        if not had_filter and not force_reload:
            return
        self.company_filter_domain = None
        self.company_result_messages = []
        self.company_folder_filter = "all"
        self._sync_company_tab_checks()
        self._sync_company_folder_filter_checks()
        self._set_company_folder_filter_visible(False)
        self._update_company_filter_badge()
        self._load_messages()

    def _open_company_manager(self):
        existing_queries = self._load_company_queries()
        dialog = CompanyTabManagerDialog(self, existing_queries)
        dialog.exec()
        if not dialog.changed:
            return

        previous_active = (self.company_filter_domain or "").strip().lower() or None
        self._save_company_queries(dialog.tabs)
        self._refresh_company_sidebar()
        if previous_active and previous_active in dialog.tabs:
            self.company_filter_domain = previous_active
            self._sync_company_tab_checks()
            self._set_company_folder_filter_visible(True)
            self._update_company_filter_badge()
            if not self.company_result_messages:
                self._load_company_messages_all_folders(previous_active)
            return
        if previous_active and previous_active not in dialog.tabs:
            self._clear_company_filter(force_reload=True)

    @staticmethod
    def _normalize_company_query(value):
        return normalize_company_query(value)

    def _load_company_queries(self):
        raw = self.config.get("companies", {}) or {}
        if isinstance(raw, dict):
            values = list(raw.keys())
        elif isinstance(raw, list):
            values = raw
        else:
            values = []
        queries = []
        for value in values:
            normalized = CompanyMixin._normalize_company_query(value)
            if normalized and normalized not in queries:
                queries.append(normalized)
        return queries

    def _save_company_queries(self, queries):
        normalized = []
        for value in queries:
            item = CompanyMixin._normalize_company_query(value)
            if item and item not in normalized:
                normalized.append(item)
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
        sender = msg.get("from", {}).get("emailAddress", {})
        address = (sender.get("address") or "").strip().lower()
        name = (sender.get("name") or "").strip().lower()

        if kind == "email":
            return address == value
        if kind == "domain":
            if "@" not in address:
                return False
            return address.split("@", 1)[1] == value
        return value in address or value in name

    def _check_detail_message_visibility(self):
        if hasattr(self, "_ensure_detail_message_visible"):
            self._ensure_detail_message_visible()


__all__ = ["CompanyMixin"]
