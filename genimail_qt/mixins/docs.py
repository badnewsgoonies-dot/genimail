import os
import shutil
import subprocess
import sys
from datetime import datetime

from PySide6.QtAxContainer import QAxWidget
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from genimail.infra.document_store import open_document_file
from genimail.paths import DEFAULT_QUOTE_TEMPLATE_FILE, QUOTE_DIR, ROOT_DIR

_DOC_EXTENSIONS = {".doc", ".docx"}
_MAX_RECENT = 20
_RECENT_SEPARATOR = "\u2500\u2500\u2500\u2500 Recently Opened \u2500\u2500\u2500\u2500"


class DocsMixin:
    _doc_preview_path = None
    _doc_preview_request_id = 0
    _docs_closing = False

    def _build_docs_tab(self):
        self._docs_closing = False
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        open_btn = QPushButton("Open Doc")
        new_from_template_btn = QPushButton("New from Template")
        open_folder_btn = QPushButton("Open Folder")
        refresh_btn = QPushButton("Refresh")
        toolbar.addWidget(open_btn)
        toolbar.addWidget(new_from_template_btn)
        toolbar.addWidget(open_folder_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # ── Splitter: file list | preview ─────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: file list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        header = QLabel("Documents")
        header.setObjectName("docsHeader")
        left_layout.addWidget(header)

        self._doc_list = QListWidget()
        self._doc_list.setSelectionMode(QAbstractItemView.SingleSelection)
        left_layout.addWidget(self._doc_list, 1)

        self._doc_empty_label = QLabel(
            "No documents found. Use 'Open Doc' or 'New from Template' to get started."
        )
        self._doc_empty_label.setWordWrap(True)
        left_layout.addWidget(self._doc_empty_label)

        left_actions = QHBoxLayout()
        remove_recent_btn = QPushButton("Remove from Recent")
        left_actions.addWidget(remove_recent_btn)
        left_actions.addStretch(1)
        left_layout.addLayout(left_actions)

        splitter.addWidget(left_panel)

        # Right panel: preview (QAxWidget created lazily on first use)
        right_panel = QWidget()
        self._doc_preview_layout = QVBoxLayout(right_panel)
        self._doc_preview_layout.setContentsMargins(0, 0, 0, 0)
        self._doc_preview_layout.setSpacing(4)

        self._doc_preview = None  # created lazily in _ensure_doc_preview()
        self._doc_preview_placeholder = QLabel("Select a document to preview it here.")
        self._doc_preview_placeholder.setAlignment(Qt.AlignCenter)
        self._doc_preview_layout.addWidget(self._doc_preview_placeholder, 1)

        preview_actions = QHBoxLayout()
        self._edit_in_word_btn = QPushButton("Edit in Word")
        self._edit_in_word_btn.setObjectName("primaryButton")
        self._close_preview_btn = QPushButton("Close Preview")
        preview_actions.addWidget(self._edit_in_word_btn)
        preview_actions.addWidget(self._close_preview_btn)
        preview_actions.addStretch(1)
        self._doc_preview_layout.addLayout(preview_actions)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 800])

        layout.addWidget(splitter, 1)

        # ── Connections ───────────────────────────────────────────
        open_btn.clicked.connect(self._open_doc_dialog)
        new_from_template_btn.clicked.connect(self._new_doc_from_template)
        open_folder_btn.clicked.connect(self._open_docs_folder)
        refresh_btn.clicked.connect(self._refresh_doc_list)
        remove_recent_btn.clicked.connect(self._remove_from_recent)
        self._doc_list.currentItemChanged.connect(self._on_doc_list_selection_changed)
        self._edit_in_word_btn.clicked.connect(self._edit_in_word)
        self._close_preview_btn.clicked.connect(self._close_doc_preview)

        self._refresh_doc_list()
        return tab

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _refresh_doc_list(self, selected_path=None):
        self._doc_list.blockSignals(True)
        self._doc_list.clear()
        selected_norm = (
            os.path.normpath(os.path.abspath(selected_path))
            if isinstance(selected_path, str) and selected_path
            else None
        )
        selected_item = None
        folder_files = []
        if os.path.isdir(QUOTE_DIR):
            for name in sorted(os.listdir(QUOTE_DIR)):
                if os.path.splitext(name)[1].lower() in _DOC_EXTENSIONS:
                    full = os.path.join(QUOTE_DIR, name)
                    if os.path.isfile(full):
                        folder_files.append(full)

        for path in folder_files:
            item = QListWidgetItem(f"{os.path.basename(path)}    quotes/")
            item.setData(256, path)  # Qt.UserRole == 256
            self._doc_list.addItem(item)
            if selected_norm and os.path.normpath(os.path.abspath(path)) == selected_norm:
                selected_item = item

        recent = self._get_recent_files()
        if recent:
            sep = QListWidgetItem(_RECENT_SEPARATOR)
            sep.setFlags(Qt.NoItemFlags)  # non-selectable separator row
            self._doc_list.addItem(sep)
            for path in recent:
                display_dir = os.path.basename(os.path.dirname(path))
                item = QListWidgetItem(f"{os.path.basename(path)}    {display_dir}")
                item.setData(256, path)
                self._doc_list.addItem(item)
                if selected_norm and os.path.normpath(os.path.abspath(path)) == selected_norm:
                    selected_item = item

        if selected_item is not None:
            self._doc_list.setCurrentItem(selected_item)

        has_items = self._doc_list.count() > 0
        self._doc_list.setVisible(has_items)
        self._doc_empty_label.setVisible(not has_items)
        self._doc_list.blockSignals(False)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _next_doc_preview_request_id(self):
        next_request_id = int(getattr(self, "_doc_preview_request_id", 0)) + 1
        self._doc_preview_request_id = next_request_id
        return next_request_id

    def _docs_cleanup(self):
        self._docs_closing = True
        self._next_doc_preview_request_id()

    def _ensure_doc_preview(self):
        """Lazily create the QAxWidget on first use (avoids blocking app startup)."""
        if self._doc_preview is not None:
            return self._doc_preview
        ax = QAxWidget()
        self._doc_preview = ax
        # Insert before the action buttons row (index 0, before placeholder)
        self._doc_preview_layout.insertWidget(0, ax, 1)
        ax.hide()
        return ax

    def _open_doc_preview(self, path, activate=False, request_id=None):
        if getattr(self, "_docs_closing", False):
            return
        if request_id is None:
            request_id = self._next_doc_preview_request_id()
        if request_id != int(getattr(self, "_doc_preview_request_id", 0)):
            return
        if not hasattr(self, "_doc_preview_layout"):
            if not open_document_file(path):
                QMessageBox.warning(self, "Open Failed", f"Could not open:\n{path}")
            return
        if not os.path.isfile(path):
            return
        abs_path = os.path.abspath(path)
        if self._doc_preview_path and os.path.normpath(self._doc_preview_path) == os.path.normpath(abs_path):
            if activate and hasattr(self, "workspace_tabs") and hasattr(self, "docs_tab"):
                self.workspace_tabs.setCurrentWidget(self.docs_tab)
            if hasattr(self, "_set_status"):
                self._set_status(f"Previewing {os.path.basename(path)}")
            return
        if request_id != int(getattr(self, "_doc_preview_request_id", 0)):
            return
        ax = self._ensure_doc_preview()
        ax.clear()  # release current COM object before loading new one
        if not ax.setControl(abs_path):
            if request_id != int(getattr(self, "_doc_preview_request_id", 0)):
                return
            self._close_doc_preview()
            if not open_document_file(path):
                QMessageBox.warning(self, "Open Failed", f"Could not open:\n{path}")
            if hasattr(self, "_set_status"):
                self._set_status(f"Preview failed — opened externally: {os.path.basename(path)}")
            return
        if request_id != int(getattr(self, "_doc_preview_request_id", 0)):
            return
        self._doc_preview_path = abs_path
        ax.show()
        self._doc_preview_placeholder.hide()
        norm = os.path.normpath(path)
        if not norm.startswith(os.path.normpath(QUOTE_DIR)):
            self._add_to_recent(path)
            self._refresh_doc_list(selected_path=abs_path)
        if activate and hasattr(self, "workspace_tabs") and hasattr(self, "docs_tab"):
            self.workspace_tabs.setCurrentWidget(self.docs_tab)
        if hasattr(self, "_set_status"):
            self._set_status(f"Previewing {os.path.basename(path)}")

    def _close_doc_preview(self):
        self._doc_preview_path = None
        if self._doc_preview is not None:
            self._doc_preview.clear()
            self._doc_preview.hide()
        if hasattr(self, "_doc_preview_placeholder"):
            self._doc_preview_placeholder.show()

    def _edit_in_word(self):
        if not self._doc_preview_path or not os.path.isfile(self._doc_preview_path):
            return
        if not open_document_file(self._doc_preview_path):
            QMessageBox.warning(self, "Open Failed", f"Could not open:\n{self._doc_preview_path}")
            return
        if hasattr(self, "_set_status"):
            self._set_status(f"Opened in Word: {os.path.basename(self._doc_preview_path)}")

    # ------------------------------------------------------------------
    # Open actions
    # ------------------------------------------------------------------

    def _open_doc_dialog(self):
        last_dir = self.config.get("docs_default_dir", "")
        if not last_dir or not os.path.isdir(last_dir):
            last_dir = QUOTE_DIR
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Document",
            last_dir,
            "Word Documents (*.doc *.docx);;All Files (*.*)",
        )
        if not path:
            return
        self.config.set("docs_default_dir", os.path.dirname(path))
        self._open_doc_preview(path, activate=True)

    def _on_doc_list_selection_changed(self, current, previous):
        if getattr(self, "_docs_closing", False):
            return
        if current is None:
            return
        path = current.data(256)
        if path:
            request_id = self._next_doc_preview_request_id()
            self._open_doc_preview(path, request_id=request_id)

    # ------------------------------------------------------------------
    # New from template
    # ------------------------------------------------------------------

    def _new_doc_from_template(self):
        template = DEFAULT_QUOTE_TEMPLATE_FILE
        if not os.path.isfile(template):
            QMessageBox.information(
                self,
                "No Template",
                f"No template found at:\n{template}\n\nPlace a .doc/.docx template there first.",
            )
            return
        os.makedirs(QUOTE_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(template)[1]
        dest = os.path.join(QUOTE_DIR, f"NewDoc_{stamp}{ext}")
        try:
            shutil.copy2(template, dest)
        except OSError as exc:
            QMessageBox.critical(self, "Copy Failed", str(exc))
            return
        self._open_doc_preview(dest, activate=True)

    # ------------------------------------------------------------------
    # Folder / recent
    # ------------------------------------------------------------------

    def _open_docs_folder(self):
        if not os.path.isdir(QUOTE_DIR):
            os.makedirs(QUOTE_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(QUOTE_DIR))

    def _get_recent_files(self):
        raw = self.config.get("docs_recent_files", [])
        if not isinstance(raw, list):
            return []
        return [p for p in raw if isinstance(p, str) and os.path.isfile(p)]

    def _add_to_recent(self, path):
        norm = os.path.normpath(os.path.abspath(path))
        recent = self.config.get("docs_recent_files", [])
        if not isinstance(recent, list):
            recent = []
        cleaned = [p for p in recent if isinstance(p, str) and os.path.normpath(p) != norm]
        cleaned.insert(0, norm)
        self.config.set("docs_recent_files", cleaned[:_MAX_RECENT])

    def _remove_from_recent(self):
        item = self._doc_list.currentItem()
        if not item:
            return
        path = item.data(256)
        if not path:
            return
        norm = os.path.normpath(os.path.abspath(path))
        recent = self.config.get("docs_recent_files", [])
        if not isinstance(recent, list):
            return
        updated = [p for p in recent if isinstance(p, str) and os.path.normpath(p) != norm]
        self.config.set("docs_recent_files", updated)
        self._refresh_doc_list()

    # ------------------------------------------------------------------
    # Scanner (called by layout.py Scan button)
    # ------------------------------------------------------------------

    def _launch_scanner(self):
        scanner_script = os.path.join(ROOT_DIR, "scanner_app_v4.py")
        if not os.path.isfile(scanner_script):
            QMessageBox.warning(self, "Scanner Missing", f"Could not find scanner script:\n{scanner_script}")
            return
        try:
            subprocess.Popen([sys.executable, scanner_script], cwd=ROOT_DIR)
            if hasattr(self, "_set_status"):
                self._set_status("Scanner opened")
        except Exception as exc:
            QMessageBox.critical(self, "Scanner Launch Failed", str(exc))


__all__ = ["DocsMixin"]
