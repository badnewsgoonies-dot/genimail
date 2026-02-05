from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from genimail.constants import APP_NAME
from genimail_qt.constants import (
    ROOT_LAYOUT_MARGINS,
    ROOT_LAYOUT_SPACING,
    TOP_BAR_MARGINS,
    TOP_BAR_SPACING,
    TOP_BAR_TITLE_SPACING,
)


class LayoutMixin:
    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(*ROOT_LAYOUT_MARGINS)
        root_layout.setSpacing(ROOT_LAYOUT_SPACING)

        top_bar = QFrame()
        self._top_bar = top_bar
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(*TOP_BAR_MARGINS)
        top_layout.setSpacing(TOP_BAR_SPACING)

        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("appTitle")
        self.status_lbl = QLabel("Disconnected")
        self.status_lbl.setObjectName("statusLabel")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primaryButton")
        self.connect_btn.clicked.connect(self._start_authentication)
        self.reconnect_btn = QPushButton("Reconnect")
        self.reconnect_btn.clicked.connect(self._reconnect)

        scan_btn = QPushButton("Scan")
        scan_btn.clicked.connect(self._launch_scanner)

        top_layout.addWidget(title_lbl)
        top_layout.addSpacing(TOP_BAR_TITLE_SPACING)
        top_layout.addWidget(self.status_lbl, 1)
        top_layout.addWidget(scan_btn)
        top_layout.addWidget(self.reconnect_btn)
        top_layout.addWidget(self.connect_btn)
        root_layout.addWidget(top_bar)

        self.workspace_tabs = QTabWidget()
        root_layout.addWidget(self.workspace_tabs, 1)
        self.internet_tab = self._build_internet_tab()
        self.email_tab = self._build_email_tab()
        self.pdf_tab = self._build_pdf_tab()
        self.docs_tab = self._build_docs_tab()

        self.workspace_tabs.addTab(self.internet_tab, "Internet")
        self.workspace_tabs.addTab(self.email_tab, "Email")
        self.workspace_tabs.addTab(self.pdf_tab, "PDF Viewer")
        self.workspace_tabs.addTab(self.docs_tab, "Docs/Templates")
        self.workspace_tabs.setCurrentWidget(self.email_tab)
        self.setCentralWidget(container)
        self._build_toast(container)


__all__ = ["LayoutMixin"]
