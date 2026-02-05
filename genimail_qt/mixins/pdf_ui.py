from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout, QWidget


class PdfUiMixin:
    def _build_pdf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        open_btn = QPushButton("Open PDF")
        close_btn = QPushButton("Close Current Tab")
        toolbar.addWidget(open_btn)
        toolbar.addWidget(close_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.pdf_tabs = QTabWidget()
        self.pdf_tabs.setTabsClosable(True)
        self.pdf_tabs.tabCloseRequested.connect(self._on_pdf_tab_close_requested)
        layout.addWidget(self.pdf_tabs, 1)

        open_btn.clicked.connect(self._open_pdf_dialog)
        close_btn.clicked.connect(self._close_current_pdf_tab)
        self._add_pdf_placeholder_tab()
        return tab


__all__ = ["PdfUiMixin"]
