from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QColorDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from genimail.domain.helpers import domain_to_company, format_date


class CompanyManagerDialog(QDialog):
    def __init__(self, parent, cache, config):
        super().__init__(parent)
        self.cache = cache
        self.config = config
        self.changed = False

        self.setWindowTitle("Company Manager")
        self.resize(820, 520)

        root_layout = QVBoxLayout(self)
        header = QLabel("Manage company labels, colors, favorites, and visibility mapped to sender domains.")
        header.setWordWrap(True)
        root_layout.addWidget(header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Domain", "Company Label", "Color", "Favorite", "Hidden", "Emails", "Last Email"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda _: self._edit_selected())
        root_layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit Label")
        self.color_btn = QPushButton("Set Color")
        self.favorite_btn = QPushButton("Toggle Favorite")
        self.hidden_btn = QPushButton("Hide/Show")
        self.auto_btn = QPushButton("Auto-Label Common")
        self.refresh_btn = QPushButton("Refresh")
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("primaryButton")
        button_row.addWidget(self.edit_btn)
        button_row.addWidget(self.color_btn)
        button_row.addWidget(self.favorite_btn)
        button_row.addWidget(self.hidden_btn)
        button_row.addWidget(self.auto_btn)
        button_row.addWidget(self.refresh_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.close_btn)
        root_layout.addLayout(button_row)

        self.edit_btn.clicked.connect(self._edit_selected)
        self.color_btn.clicked.connect(self._pick_selected_color)
        self.favorite_btn.clicked.connect(self._toggle_selected_favorite)
        self.hidden_btn.clicked.connect(self._toggle_selected_hidden)
        self.auto_btn.clicked.connect(self._auto_label)
        self.refresh_btn.clicked.connect(self._load_data)
        self.close_btn.clicked.connect(self.accept)

        self._load_data()

    def _load_data(self):
        self.table.setRowCount(0)
        try:
            domains = self.cache.get_all_domains()
        except Exception as exc:
            QMessageBox.warning(self, "Load Error", str(exc))
            return

        companies_cfg = self.config.get("companies", {}) or {}
        colors_cfg = self.config.get("company_colors", {}) or {}
        favorites = self._get_domain_set("company_favorites")
        hidden = self._get_domain_set("company_hidden")

        rows_by_domain = {}
        for domain_data in domains:
            domain = (domain_data.get("domain") or "").strip().lower()
            if domain:
                rows_by_domain[domain] = domain_data

        domain_pool = set(rows_by_domain.keys())
        domain_pool.update((domain or "").strip().lower() for domain in companies_cfg.keys())
        domain_pool.update((domain or "").strip().lower() for domain in colors_cfg.keys())
        domain_pool.update(favorites)
        domain_pool.update(hidden)
        domain_pool = {domain for domain in domain_pool if domain}

        for domain in sorted(domain_pool):
            domain_data = rows_by_domain.get(domain, {})
            row = self.table.rowCount()
            self.table.insertRow(row)
            label = domain_data.get("company_label") or companies_cfg.get(domain) or domain_to_company(domain)
            count = str(domain_data.get("count") or 0)
            last_email = format_date(domain_data.get("last_email") or "")
            color_hex = colors_cfg.get(domain) or ""
            favorite_text = "Yes" if domain in favorites else ""
            hidden_text = "Yes" if domain in hidden else ""

            domain_item = QTableWidgetItem(domain)
            label_item = QTableWidgetItem(label)
            color_item = QTableWidgetItem(color_hex)
            favorite_item = QTableWidgetItem(favorite_text)
            hidden_item = QTableWidgetItem(hidden_text)
            count_item = QTableWidgetItem(count)
            last_item = QTableWidgetItem(last_email)

            domain_item.setData(Qt.UserRole, domain)
            if color_hex:
                color = QColor(color_hex)
                if color.isValid():
                    color_item.setBackground(color)
                    if color.lightness() < 120:
                        color_item.setForeground(QColor("#ffffff"))
            if domain in hidden:
                for item in (domain_item, label_item, color_item, favorite_item, hidden_item, count_item, last_item):
                    item.setForeground(Qt.darkGray)
            elif domain in favorites:
                for item in (domain_item, label_item):
                    item.setForeground(QColor("#7a5800"))

            self.table.setItem(row, 0, domain_item)
            self.table.setItem(row, 1, label_item)
            self.table.setItem(row, 2, color_item)
            self.table.setItem(row, 3, favorite_item)
            self.table.setItem(row, 4, hidden_item)
            self.table.setItem(row, 5, count_item)
            self.table.setItem(row, 6, last_item)

        self.table.resizeColumnsToContents()

    def _get_domain_set(self, key):
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

    def _save_domain_set(self, key, domains):
        ordered = sorted({(domain or "").strip().lower() for domain in domains if (domain or "").strip()})
        self.config.set(key, ordered)

    def _selected_domain(self):
        row = self.table.currentRow()
        if row < 0:
            return None, ""
        domain_item = self.table.item(row, 0)
        label_item = self.table.item(row, 1)
        if domain_item is None:
            return None, ""
        return domain_item.data(Qt.UserRole), (label_item.text() if label_item else "")

    def _edit_selected(self):
        domain, current_label = self._selected_domain()
        if not domain:
            QMessageBox.information(self, "No Selection", "Select a domain first.")
            return

        new_label, ok = QInputDialog.getText(
            self,
            f"Label: {domain}",
            f"Company label for @{domain}:",
            text=current_label,
        )
        if not ok:
            return

        normalized = new_label.strip()
        self.cache.label_domain(domain, normalized if normalized else None)
        companies = self.config.get("companies", {}) or {}
        if normalized:
            companies[domain] = normalized
        else:
            companies.pop(domain, None)
        self.config.set("companies", companies)
        self.changed = True
        self._load_data()

    def _toggle_selected_favorite(self):
        domain, _ = self._selected_domain()
        if not domain:
            QMessageBox.information(self, "No Selection", "Select a domain first.")
            return
        favorites = self._get_domain_set("company_favorites")
        if domain in favorites:
            favorites.remove(domain)
        else:
            favorites.add(domain)
        self._save_domain_set("company_favorites", favorites)
        self.changed = True
        self._load_data()

    def _toggle_selected_hidden(self):
        domain, _ = self._selected_domain()
        if not domain:
            QMessageBox.information(self, "No Selection", "Select a domain first.")
            return
        hidden = self._get_domain_set("company_hidden")
        if domain in hidden:
            hidden.remove(domain)
        else:
            hidden.add(domain)
        self._save_domain_set("company_hidden", hidden)
        self.changed = True
        self._load_data()

    def _pick_selected_color(self):
        domain, _ = self._selected_domain()
        if not domain:
            QMessageBox.information(self, "No Selection", "Select a domain first.")
            return
        colors_cfg = self.config.get("company_colors", {}) or {}
        initial = QColor(colors_cfg.get(domain) or "#E07A5F")
        selected = QColorDialog.getColor(initial, self, f"Choose color for @{domain}")
        if not selected.isValid():
            return
        colors_cfg[domain] = selected.name()
        self.config.set("company_colors", colors_cfg)
        self.changed = True
        self._load_data()

    def _auto_label(self):
        known_domains = {
            "gmail.com": "Google",
            "outlook.com": "Microsoft",
            "hotmail.com": "Microsoft",
            "mail.com": "Mail.com",
            "yahoo.com": "Yahoo",
            "icloud.com": "Apple",
            "me.com": "Apple",
            "aol.com": "AOL",
            "verizon.net": "Verizon",
            "comcast.net": "Comcast",
            "rogers.com": "Rogers",
            "bell.net": "Bell",
            "telus.net": "Telus",
            "shaw.ca": "Shaw",
            "bcpl.ca": "BC Public Library",
            "td.com": "TD",
            "rbc.com": "RBC",
            "bmo.com": "BMO",
            "scotiabank.com": "Scotiabank",
            "cibc.com": "CIBC",
            "apple.com": "Apple",
            "amazon.com": "Amazon",
            "amazon.ca": "Amazon",
            "walmart.com": "Walmart",
            "walmart.ca": "Walmart",
            "homedepot.com": "Home Depot",
            "homedepot.ca": "Home Depot",
            "costco.com": "Costco",
            "costco.ca": "Costco",
            "lowes.com": "Lowe's",
            "lowes.ca": "Lowe's",
            "ups.com": "UPS",
            "fedex.com": "FedEx",
            "dhl.com": "DHL",
            "canadapost.ca": "Canada Post",
            "cra-arc.gc.ca": "CRA",
            "ontario.ca": "Ontario",
            "gov.on.ca": "Ontario",
            "canada.ca": "Canada",
            "paypal.com": "PayPal",
            "squareup.com": "Square",
            "quickbooks.intuit.com": "QuickBooks",
            "freshbooks.com": "FreshBooks",
            "xero.com": "Xero",
            "stripe.com": "Stripe",
            "docusign.com": "DocuSign",
            "docusign.net": "DocuSign",
            "interac.ca": "Interac",
            "instagram.com": "Instagram",
            "facebook.com": "Facebook",
            "linkedin.com": "LinkedIn",
            "github.com": "GitHub",
            "bitbucket.org": "Bitbucket",
            "slack.com": "Slack",
            "zoom.us": "Zoom",
            "teams.microsoft.com": "Microsoft Teams",
            "google.com": "Google",
            "youtube.com": "YouTube",
            "netflix.com": "Netflix",
            "spotify.com": "Spotify",
            "tiktok.com": "TikTok",
            "ubereats.com": "Uber Eats",
            "doordash.com": "DoorDash",
            "shopify.com": "Shopify",
        }
        labeled_count = 0
        companies = self.config.get("companies", {}) or {}
        for domain, label in known_domains.items():
            count = self.cache.label_domain(domain, label)
            if count > 0:
                labeled_count += count
                companies[domain] = label
        self.config.set("companies", companies)
        self.changed = labeled_count > 0 or self.changed
        self._load_data()
        QMessageBox.information(
            self,
            "Auto-Label Complete",
            f"Labeled {labeled_count} email(s) from known companies.",
        )


__all__ = ["CompanyManagerDialog"]
