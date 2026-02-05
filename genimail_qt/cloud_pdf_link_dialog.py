from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout


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


__all__ = ["CloudPdfLinkDialog"]
