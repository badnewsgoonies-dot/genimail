from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from genimail.constants import INTERNET_DEFAULT_URL


class InternetMixin:
    def _build_internet_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()

        self.web_back_btn = QPushButton("Back")
        self.web_forward_btn = QPushButton("Forward")
        self.web_reload_btn = QPushButton("Reload")
        self.web_url_input = QLineEdit("https://")
        self.web_go_btn = QPushButton("Go")
        self.web_go_btn.setObjectName("primaryButton")
        toolbar.addWidget(self.web_back_btn)
        toolbar.addWidget(self.web_forward_btn)
        toolbar.addWidget(self.web_reload_btn)
        toolbar.addWidget(self.web_url_input, 1)
        toolbar.addWidget(self.web_go_btn)
        layout.addLayout(toolbar)

        self.internet_view = self._create_web_view("internet")
        self.internet_view.setUrl(QUrl(INTERNET_DEFAULT_URL))
        layout.addWidget(self.internet_view, 1)

        self.web_back_btn.clicked.connect(self.internet_view.back)
        self.web_forward_btn.clicked.connect(self.internet_view.forward)
        self.web_reload_btn.clicked.connect(self.internet_view.reload)
        self.web_go_btn.clicked.connect(self._navigate_internet)
        self.web_url_input.returnPressed.connect(self._navigate_internet)
        self.internet_view.urlChanged.connect(self._on_internet_url_changed)
        return tab

    def _navigate_internet(self):
        raw = self.web_url_input.text().strip()
        if not raw:
            return
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        self.internet_view.setUrl(QUrl(raw))

    def _on_internet_url_changed(self, url):
        if url:
            self.web_url_input.setText(url.toString())


__all__ = ["InternetMixin"]
