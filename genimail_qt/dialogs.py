from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from genimail.domain.helpers import format_date


class CompanyManagerDialog(QDialog):
    def __init__(self, parent, cache, config):
        super().__init__(parent)
        self.cache = cache
        self.config = config
        self.changed = False

        self.setWindowTitle("Company Manager")
        self.resize(820, 520)

        root_layout = QVBoxLayout(self)
        header = QLabel("Manage company labels mapped to sender domains")
        header.setWordWrap(True)
        root_layout.addWidget(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Domain", "Company Label", "Emails", "Last Email"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda _: self._edit_selected())
        root_layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit Label")
        self.auto_btn = QPushButton("Auto-Label Common")
        self.refresh_btn = QPushButton("Refresh")
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("primaryButton")
        button_row.addWidget(self.edit_btn)
        button_row.addWidget(self.auto_btn)
        button_row.addWidget(self.refresh_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.close_btn)
        root_layout.addLayout(button_row)

        self.edit_btn.clicked.connect(self._edit_selected)
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

        for domain_data in domains:
            row = self.table.rowCount()
            self.table.insertRow(row)
            domain = domain_data.get("domain") or ""
            label = domain_data.get("company_label") or ""
            count = str(domain_data.get("count") or 0)
            last_email = format_date(domain_data.get("last_email") or "")

            domain_item = QTableWidgetItem(domain)
            label_item = QTableWidgetItem(label)
            count_item = QTableWidgetItem(count)
            last_item = QTableWidgetItem(last_email)

            domain_item.setData(Qt.UserRole, domain)
            if not label:
                for item in (domain_item, label_item, count_item, last_item):
                    item.setForeground(Qt.darkGray)

            self.table.setItem(row, 0, domain_item)
            self.table.setItem(row, 1, label_item)
            self.table.setItem(row, 2, count_item)
            self.table.setItem(row, 3, last_item)

        self.table.resizeColumnsToContents()

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

    def _auto_label(self):
        known_domains = {
            "amazon.com": "Amazon",
            "amazon.ca": "Amazon",
            "google.com": "Google",
            "gmail.com": "Gmail",
            "microsoft.com": "Microsoft",
            "outlook.com": "Outlook",
            "apple.com": "Apple",
            "icloud.com": "iCloud",
            "paypal.com": "PayPal",
            "paypal.ca": "PayPal",
            "facebook.com": "Facebook",
            "meta.com": "Meta",
            "twitter.com": "Twitter",
            "x.com": "X",
            "linkedin.com": "LinkedIn",
            "netflix.com": "Netflix",
            "spotify.com": "Spotify",
            "uber.com": "Uber",
            "ubereats.com": "Uber Eats",
            "doordash.com": "DoorDash",
            "shopify.com": "Shopify",
            "stripe.com": "Stripe",
            "github.com": "GitHub",
            "docusign.com": "DocuSign",
            "docusign.net": "DocuSign",
            "interac.ca": "Interac",
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


class CloudPdfLinkDialog(QDialog):
    def __init__(self, parent, links):
        super().__init__(parent)
        self.links = list(links or [])
        self.setWindowTitle("Linked Cloud PDFs")
        self.resize(820, 460)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(QLabel("Select cloud/external PDF links to download and open in PDF tabs."))

        self.link_list = QListWidget()
        root_layout.addWidget(self.link_list, 1)

        for link in self.links:
            source = link.get("source", "External")
            name = link.get("suggested_name", "linked.pdf")
            url = link.get("original_url", "")
            text = f"{source} · {name}\n{url}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, link)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.link_list.addItem(item)

        button_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.clear_btn = QPushButton("Clear")
        self.cancel_btn = QPushButton("Cancel")
        self.open_btn = QPushButton("Open Selected")
        self.open_btn.setObjectName("primaryButton")
        button_row.addWidget(self.select_all_btn)
        button_row.addWidget(self.clear_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.open_btn)
        root_layout.addLayout(button_row)

        self.select_all_btn.clicked.connect(self._select_all)
        self.clear_btn.clicked.connect(self._clear_all)
        self.cancel_btn.clicked.connect(self.reject)
        self.open_btn.clicked.connect(self.accept)

    def _select_all(self):
        for idx in range(self.link_list.count()):
            self.link_list.item(idx).setCheckState(Qt.Checked)

    def _clear_all(self):
        for idx in range(self.link_list.count()):
            self.link_list.item(idx).setCheckState(Qt.Unchecked)

    def selected_links(self):
        selected = []
        for idx in range(self.link_list.count()):
            item = self.link_list.item(idx)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected
