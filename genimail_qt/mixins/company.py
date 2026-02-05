from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QListWidgetItem, QMessageBox

from genimail.constants import FOLDER_DISPLAY
from genimail.domain.helpers import domain_to_company
from genimail_qt.constants import (
    COMPANY_COLLAPSE_ICON_COLLAPSED,
    COMPANY_COLLAPSE_ICON_EXPANDED,
    COMPANY_STAR_ICON,
)
from genimail_qt.dialogs import CompanyManagerDialog


class CompanyMixin:
    def _populate_folders(self, folders):
        self.folder_list.clear()
        sorted_folders = sorted(
            folders,
            key=lambda item: (
                0 if item.get("displayName", "").lower() in FOLDER_DISPLAY else 1,
                item.get("displayName", "").lower(),
            ),
        )
        for folder in sorted_folders:
            folder_name = folder.get("displayName", "")
            display_name = FOLDER_DISPLAY.get(folder_name.lower(), folder_name)
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, folder)
            self.folder_list.addItem(item)
            if folder_name.lower() == "inbox":
                self.folder_list.setCurrentItem(item)
        if self.folder_list.currentRow() < 0 and self.folder_list.count() > 0:
            self.folder_list.setCurrentRow(0)

    def _refresh_company_sidebar(self):
        self.company_list.blockSignals(True)
        self.company_list.clear()
        self.company_domain_labels = {}

        all_item = QListWidgetItem("All Companies")
        all_item.setData(Qt.UserRole, None)
        all_item.setToolTip("Show messages from every company")
        self.company_list.addItem(all_item)

        companies_cfg = self.config.get("companies", {}) or {}
        colors_cfg = self.config.get("company_colors", {}) or {}
        favorites = self._get_company_domain_set("company_favorites")
        hidden = self._get_company_domain_set("company_hidden")
        order_list = [
            (domain or "").strip().lower()
            for domain in (self.config.get("company_order", []) or [])
            if (domain or "").strip()
        ]
        order_index = {domain: idx for idx, domain in enumerate(order_list)}

        try:
            domain_rows = self.cache.get_all_domains()
        except Exception:
            domain_rows = []
        rows_by_domain = {}
        for row in domain_rows:
            domain = (row.get("domain") or "").strip().lower()
            if domain:
                rows_by_domain[domain] = row

        domain_pool = set(rows_by_domain.keys())
        domain_pool.update((domain or "").strip().lower() for domain in companies_cfg.keys())
        domain_pool.update((domain or "").strip().lower() for domain in colors_cfg.keys())
        domain_pool.update(favorites)
        domain_pool.update(hidden)
        domain_pool.update(order_index.keys())
        domain_pool = {domain for domain in domain_pool if domain}

        entries = []
        for domain in domain_pool:
            row = rows_by_domain.get(domain, {})
            label = row.get("company_label") or companies_cfg.get(domain) or domain_to_company(domain)
            count = row.get("count") or 0
            entry = {
                "domain": domain,
                "label": label,
                "count": count,
                "favorite": domain in favorites,
                "hidden": domain in hidden,
                "color": colors_cfg.get(domain),
                "order": order_index.get(domain),
            }
            entries.append(entry)
            self.company_domain_labels[domain] = label

        visible_entries = [entry for entry in entries if not entry["hidden"]]
        visible_entries.sort(
            key=lambda entry: (
                0 if entry["favorite"] else 1,
                entry["order"] if entry["order"] is not None else 10_000,
                entry["label"].lower(),
                entry["domain"],
            )
        )

        if self.company_filter_domain and self.company_filter_domain not in {entry["domain"] for entry in visible_entries}:
            self.company_filter_domain = None

        for entry in visible_entries:
            star = f"{COMPANY_STAR_ICON} " if entry["favorite"] else ""
            count = int(entry.get("count") or 0)
            item = QListWidgetItem(f"{star}{entry['label']}\n@{entry['domain']} · {count} email(s)")
            item.setData(Qt.UserRole, entry["domain"])
            item.setToolTip(f"Filter messages from @{entry['domain']}")
            color_hex = entry.get("color")
            if color_hex:
                color = QColor(color_hex)
                if color.isValid():
                    item.setForeground(color)
            if entry["favorite"]:
                item.setBackground(QColor("#fff8e6"))
            self.company_list.addItem(item)

        target_index = 0
        if self.company_filter_domain:
            for idx in range(self.company_list.count()):
                item = self.company_list.item(idx)
                if item.data(Qt.UserRole) == self.company_filter_domain:
                    target_index = idx
                    break
        self.company_list.setCurrentRow(target_index)
        self._update_company_section_header()
        self._update_company_filter_badge()
        self._update_company_inline_buttons()
        self.company_list.blockSignals(False)

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

    def _toggle_company_section_from_button(self):
        self._set_company_collapsed(not self.company_section_btn.isChecked(), persist=True)

    def _set_company_collapsed(self, collapsed, persist=True):
        if persist:
            self.config.set("company_collapsed", bool(collapsed))
        self.company_body.setVisible(not collapsed)
        self.company_section_btn.blockSignals(True)
        self.company_section_btn.setChecked(not collapsed)
        self.company_section_btn.blockSignals(False)
        self._update_company_section_header()

    def _update_company_section_header(self):
        collapsed = bool(self.config.get("company_collapsed", False))
        icon = COMPANY_COLLAPSE_ICON_COLLAPSED if collapsed else COMPANY_COLLAPSE_ICON_EXPANDED
        visible_count = max(0, self.company_list.count() - 1)
        self.company_section_btn.setText(f"{icon} Companies ({visible_count})")

    def _update_company_filter_badge(self):
        domain = (self.company_filter_domain or "").strip().lower()
        if not domain:
            self.company_filter_badge.hide()
            self.clear_company_filter_btn.hide()
            return
        label = self.company_domain_labels.get(domain) or domain_to_company(domain)
        self.company_filter_badge.setText(f"Filtered: {label} (@{domain})")
        self.company_filter_badge.show()
        self.clear_company_filter_btn.show()

    def _selected_company_domain(self):
        item = self.company_list.currentItem()
        if item is None:
            return None
        domain = item.data(Qt.UserRole)
        return (domain or "").strip().lower() or None

    def _update_company_inline_buttons(self):
        domain = self._selected_company_domain()
        enabled = bool(domain)
        self.company_favorite_btn.setEnabled(enabled)
        self.company_hide_btn.setEnabled(enabled)
        self.company_color_btn.setEnabled(enabled)
        if not enabled:
            self.company_favorite_btn.setText(f"{COMPANY_STAR_ICON} Favorite")
            self.company_hide_btn.setText("Hide")
            self.company_color_btn.setText("Color")
            return
        favorites = self._get_company_domain_set("company_favorites")
        hidden = self._get_company_domain_set("company_hidden")
        self.company_favorite_btn.setText(
            f"{COMPANY_STAR_ICON} Unfavorite" if domain in favorites else f"{COMPANY_STAR_ICON} Favorite"
        )
        self.company_hide_btn.setText("Show" if domain in hidden else "Hide")
        colors_cfg = self.config.get("company_colors", {}) or {}
        self.company_color_btn.setText("Color ✓" if colors_cfg.get(domain) else "Color")

    def _clear_company_filter(self):
        if not self.company_filter_domain:
            return
        self.company_filter_domain = None
        self._render_message_list()
        self._check_detail_message_visibility()
        self.company_list.blockSignals(True)
        if self.company_list.count() > 0:
            self.company_list.setCurrentRow(0)
        self.company_list.blockSignals(False)
        self._update_company_filter_badge()
        self._update_company_inline_buttons()
        self._set_status(f"Showing {len(self.filtered_messages)} message(s)")

    def _toggle_selected_company_favorite(self):
        domain = self._selected_company_domain()
        if not domain:
            return
        favorites = self._get_company_domain_set("company_favorites")
        if domain in favorites:
            favorites.remove(domain)
        else:
            favorites.add(domain)
        self._save_company_domain_set("company_favorites", favorites)
        self._refresh_company_sidebar()

    def _toggle_selected_company_hidden(self):
        domain = self._selected_company_domain()
        if not domain:
            return
        hidden = self._get_company_domain_set("company_hidden")
        now_hidden = False
        if domain in hidden:
            hidden.remove(domain)
        else:
            hidden.add(domain)
            now_hidden = True
        self._save_company_domain_set("company_hidden", hidden)
        if now_hidden and domain == self.company_filter_domain:
            self.company_filter_domain = None
            self._render_message_list()
        self._refresh_company_sidebar()
        self._check_detail_message_visibility()

    def _pick_selected_company_color(self):
        domain = self._selected_company_domain()
        if not domain:
            return
        colors_cfg = self.config.get("company_colors", {}) or {}
        initial = QColor(colors_cfg.get(domain) or "#1f6feb")
        selected = QColorDialog.getColor(initial, self, f"Choose color for @{domain}")
        if not selected.isValid():
            return
        colors_cfg[domain] = selected.name()
        self.config.set("company_colors", colors_cfg)
        self._refresh_company_sidebar()

    def _on_company_item_clicked(self, item):
        if item is None:
            return
        domain = (item.data(Qt.UserRole) or "").strip().lower()
        if domain and domain == self.company_filter_domain:
            self._clear_company_filter()

    def _on_company_filter_changed(self, row):
        if row < 0:
            return
        item = self.company_list.item(row)
        if item is None:
            return
        selected_domain = item.data(Qt.UserRole)
        self.company_filter_domain = (selected_domain or "").strip().lower() or None
        self._render_message_list()
        self._check_detail_message_visibility()
        self._update_company_filter_badge()
        self._update_company_inline_buttons()
        self._set_status(
            f"Showing {len(self.filtered_messages)} message(s)"
            + (f" for @{self.company_filter_domain}" if self.company_filter_domain else "")
        )

    def _open_company_manager(self):
        dialog = CompanyManagerDialog(self, self.cache, self.config)
        dialog.exec()
        if dialog.changed:
            self._refresh_company_sidebar()
            self._render_message_list()
            self._check_detail_message_visibility()

    def _check_detail_message_visibility(self):
        if hasattr(self, "_ensure_detail_message_visible"):
            self._ensure_detail_message_visible()

    def _on_folder_changed(self, row):
        if row < 0:
            return
        item = self.folder_list.item(row)
        if item is None:
            return
        folder = item.data(Qt.UserRole) or {}
        self._show_message_list()
        self._clear_detail_view()
        self.current_folder_id = folder.get("id") or "inbox"
        self._load_messages()


__all__ = ["CompanyMixin"]
