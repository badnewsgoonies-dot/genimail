import base64
import os
import subprocess
import sys
import threading
from functools import partial

from PySide6.QtCore import Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    HAS_QTPDF = True
except Exception:
    QPdfDocument = None
    QPdfView = None
    HAS_QTPDF = False

from genimail.browser import BrowserDownloadError
from genimail.browser.navigation import ensure_light_preview_html, wrap_plain_text_as_html
from genimail.constants import (
    APP_NAME,
    CLOUD_PDF_FAILURE_PREVIEW_MAX,
    CLOUD_PDF_SOURCE_SUMMARY_MAX,
    DEFAULT_CLIENT_ID,
    EMAIL_DELTA_FALLBACK_TOP,
    EMAIL_LIST_FETCH_TOP,
    FOLDER_DISPLAY,
    INTERNET_DEFAULT_URL,
    POLL_INTERVAL_MS,
    QT_SPLITTER_LEFT_DEFAULT,
    QT_SPLITTER_RIGHT_DEFAULT,
    QT_THREAD_POOL_MAX_WORKERS,
    QT_WINDOW_DEFAULT_GEOMETRY,
    QT_WINDOW_MIN_HEIGHT,
    QT_WINDOW_MIN_WIDTH,
    TAKEOFF_DEFAULT_COATS,
)
from genimail.domain.helpers import (
    build_reply_recipients,
    domain_to_company,
    format_date,
    format_size,
    strip_html,
    token_cache_path_for_client_id,
)
from genimail.domain.link_tools import collect_cloud_pdf_links
from genimail.domain.quotes import build_quote_context, create_quote_doc, open_document_file
from genimail.infra.cache_store import EmailCache
from genimail.infra.config_store import Config
from genimail.infra.graph_client import GraphClient
from genimail.paths import DEFAULT_QUOTE_TEMPLATE_FILE, PDF_DIR, QUOTE_DIR, ROOT_DIR
from genimail.services.mail_sync import MailSyncService, collect_new_unread
from genimail_qt.cloud_pdf_cache import CloudPdfCache
from genimail_qt.dialogs import CloudPdfLinkDialog, CompanyManagerDialog
from genimail_qt.takeoff_engine import compute_takeoff, estimate_door_count, parse_length_to_feet
from genimail_qt.workers import Worker


class ComposeDialog(QDialog):
    def __init__(self, parent, mode_label, defaults, on_send):
        super().__init__(parent)
        self._on_send = on_send
        self._attachments = []
        self.setWindowTitle(f"{mode_label} - {APP_NAME}")
        self.resize(780, 620)

        root_layout = QVBoxLayout(self)

        form = QFormLayout()
        self.to_input = QLineEdit(defaults.get("to", ""))
        self.cc_input = QLineEdit(defaults.get("cc", ""))
        self.subject_input = QLineEdit(defaults.get("subject", ""))
        form.addRow("To", self.to_input)
        form.addRow("CC", self.cc_input)
        form.addRow("Subject", self.subject_input)
        root_layout.addLayout(form)

        self.body_input = QTextEdit(defaults.get("body", ""))
        self.body_input.setPlaceholderText("Write your message...")
        root_layout.addWidget(self.body_input, 1)

        attach_box = QGroupBox("Attachments")
        attach_layout = QVBoxLayout(attach_box)
        self.attach_list = QListWidget()
        attach_layout.addWidget(self.attach_list, 1)
        attach_row = QHBoxLayout()
        self.add_attach_btn = QPushButton("Add Files")
        self.remove_attach_btn = QPushButton("Remove Selected")
        attach_row.addWidget(self.add_attach_btn)
        attach_row.addWidget(self.remove_attach_btn)
        attach_row.addStretch(1)
        attach_layout.addLayout(attach_row)
        root_layout.addWidget(attach_box)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        bottom_row.addWidget(self.send_btn)
        bottom_row.addWidget(cancel_btn)
        root_layout.addLayout(bottom_row)

        self.add_attach_btn.clicked.connect(self._on_add_attachment)
        self.remove_attach_btn.clicked.connect(self._on_remove_attachment)
        self.send_btn.clicked.connect(self._on_send_clicked)
        cancel_btn.clicked.connect(self.reject)

    def _on_add_attachment(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if not files:
            return
        for path in files:
            normalized = os.path.abspath(path)
            if normalized in self._attachments:
                continue
            self._attachments.append(normalized)
            self.attach_list.addItem(normalized)

    def _on_remove_attachment(self):
        row = self.attach_list.currentRow()
        if row < 0:
            return
        self.attach_list.takeItem(row)
        self._attachments.pop(row)

    def _on_send_clicked(self):
        payload = self._collect_payload()
        if payload is None:
            return
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending...")
        self._on_send(payload, self)

    def _collect_payload(self):
        to_list = [item.strip() for item in self.to_input.text().split(";") if item.strip()]
        if not to_list:
            QMessageBox.warning(self, "Missing Recipient", "Add at least one recipient in To.")
            return None

        cc_list = [item.strip() for item in self.cc_input.text().split(";") if item.strip()]
        subject = self.subject_input.text().strip()
        body = self.body_input.toPlainText()

        attachments = []
        for path in self._attachments:
            try:
                with open(path, "rb") as handle:
                    encoded = base64.b64encode(handle.read()).decode("utf-8")
                attachments.append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(path),
                        "contentBytes": encoded,
                    }
                )
            except OSError as exc:
                QMessageBox.warning(self, "Attachment Error", f"Could not read attachment:\n{path}\n\n{exc}")
                return None

        return {
            "to": to_list,
            "cc": cc_list,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        }

    def mark_send_failed(self, message):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        QMessageBox.critical(self, "Send Failed", message)


class GeniMailQtWindow(QMainWindow):
    auth_code_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.cache = EmailCache()
        self.cloud_pdf_cache = CloudPdfCache(self.cache, self.config.get)
        self.graph = None
        self.sync_service = None
        self.current_user_email = ""
        self.current_folder_id = "inbox"
        self.current_messages = []
        self.filtered_messages = []
        self.current_message = None
        self.message_cache = {}
        self.attachment_cache = {}
        self.cloud_link_cache = {}
        self.known_ids = set()
        self.company_filter_domain = None
        self._poll_in_flight = False
        self._poll_lock = threading.Lock()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(QT_THREAD_POOL_MAX_WORKERS)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_once)

        self._build_ui()
        self._restore_window_geometry()
        self.auth_code_received.connect(self._show_auth_code_dialog)

    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(8)

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
        top_layout.addSpacing(12)
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

        self.internet_view = QWebEngineView()
        self.internet_view.setUrl(QUrl(INTERNET_DEFAULT_URL))
        layout.addWidget(self.internet_view, 1)

        self.web_back_btn.clicked.connect(self.internet_view.back)
        self.web_forward_btn.clicked.connect(self.internet_view.forward)
        self.web_reload_btn.clicked.connect(self.internet_view.reload)
        self.web_go_btn.clicked.connect(self._navigate_internet)
        self.web_url_input.returnPressed.connect(self._navigate_internet)
        self.internet_view.urlChanged.connect(self._on_internet_url_changed)
        return tab

    def _build_email_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search emails...")
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primaryButton")
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_btn)
        left_layout.addLayout(search_row)
        left_layout.addWidget(QLabel("Folders"))
        self.folder_list = QListWidget()
        left_layout.addWidget(self.folder_list, 1)

        company_header = QHBoxLayout()
        company_header.addWidget(QLabel("Companies"))
        self.manage_companies_btn = QPushButton("Manage")
        company_header.addWidget(self.manage_companies_btn)
        left_layout.addLayout(company_header)
        self.company_list = QListWidget()
        left_layout.addWidget(self.company_list, 1)

        left_layout.addWidget(QLabel("Messages"))
        self.message_list = QListWidget()
        left_layout.addWidget(self.message_list, 2)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.message_header = QLabel("Select a message")
        right_layout.addWidget(self.message_header)

        self.email_preview = QWebEngineView()
        self.email_preview.setHtml("<html><body style='font-family:Segoe UI;'>No message selected.</body></html>")
        right_layout.addWidget(self.email_preview, 1)

        attach_box = QGroupBox("Attachments")
        attach_layout = QVBoxLayout(attach_box)
        self.attachment_list = QListWidget()
        attach_layout.addWidget(self.attachment_list, 1)
        self.cloud_links_info = QLabel("No linked cloud files found")
        attach_layout.addWidget(self.cloud_links_info)
        attach_buttons = QHBoxLayout()
        self.open_attachment_btn = QPushButton("Open Selected")
        self.save_attachment_btn = QPushButton("Save Selected As...")
        self.open_cloud_links_btn = QPushButton("Open Linked PDFs")
        self.open_cloud_links_btn.setEnabled(False)
        attach_buttons.addWidget(self.open_attachment_btn)
        attach_buttons.addWidget(self.save_attachment_btn)
        attach_buttons.addWidget(self.open_cloud_links_btn)
        attach_buttons.addStretch(1)
        attach_layout.addLayout(attach_buttons)
        right_layout.addWidget(attach_box)

        action_row = QHBoxLayout()
        self.reply_btn = QPushButton("Reply")
        self.reply_all_btn = QPushButton("Reply All")
        self.forward_btn = QPushButton("Forward")
        self.new_mail_btn = QPushButton("New Email")
        self.new_mail_btn.setObjectName("primaryButton")
        action_row.addWidget(self.reply_btn)
        action_row.addWidget(self.reply_all_btn)
        action_row.addWidget(self.forward_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.new_mail_btn)
        right_layout.addLayout(action_row)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([QT_SPLITTER_LEFT_DEFAULT, QT_SPLITTER_RIGHT_DEFAULT])

        self.folder_list.currentRowChanged.connect(self._on_folder_changed)
        self.company_list.currentRowChanged.connect(self._on_company_filter_changed)
        self.manage_companies_btn.clicked.connect(self._open_company_manager)
        self.search_btn.clicked.connect(self._load_messages)
        self.search_input.returnPressed.connect(self._load_messages)
        self.message_list.currentRowChanged.connect(self._on_message_selected)
        self.open_attachment_btn.clicked.connect(self._open_selected_attachment)
        self.save_attachment_btn.clicked.connect(self._save_selected_attachment)
        self.open_cloud_links_btn.clicked.connect(self._open_cloud_links_for_current)
        self.new_mail_btn.clicked.connect(lambda: self._open_compose_dialog("new"))
        self.reply_btn.clicked.connect(lambda: self._open_compose_dialog("reply"))
        self.reply_all_btn.clicked.connect(lambda: self._open_compose_dialog("reply_all"))
        self.forward_btn.clicked.connect(lambda: self._open_compose_dialog("forward"))
        return tab

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

    def _build_docs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        quote_group = QGroupBox("Quote Builder")
        quote_layout = QFormLayout(quote_group)
        self.quote_template_input = QLineEdit(self.config.get("quote_template_path", DEFAULT_QUOTE_TEMPLATE_FILE))
        self.quote_output_input = QLineEdit(self.config.get("quote_output_dir", QUOTE_DIR))
        self.quote_client_input = QLineEdit("")
        self.quote_email_input = QLineEdit("")
        self.quote_project_input = QLineEdit("")
        self.quote_reference_input = QLineEdit("")
        quote_layout.addRow("Template File", self.quote_template_input)
        quote_layout.addRow("Output Folder", self.quote_output_input)
        quote_layout.addRow("Client Name", self.quote_client_input)
        quote_layout.addRow("Client Email", self.quote_email_input)
        quote_layout.addRow("Project Name", self.quote_project_input)
        quote_layout.addRow("Reference", self.quote_reference_input)
        layout.addWidget(quote_group)

        quote_actions = QHBoxLayout()
        browse_template_btn = QPushButton("Browse Template")
        browse_output_btn = QPushButton("Browse Output")
        create_quote_btn = QPushButton("Create Quote Doc")
        create_quote_btn.setObjectName("primaryButton")
        open_output_btn = QPushButton("Open Quotes Folder")
        quote_actions.addWidget(browse_template_btn)
        quote_actions.addWidget(browse_output_btn)
        quote_actions.addWidget(create_quote_btn)
        quote_actions.addWidget(open_output_btn)
        quote_actions.addStretch(1)
        layout.addLayout(quote_actions)

        takeoff_group = QGroupBox("Takeoff (Beta)")
        takeoff_layout = QFormLayout(takeoff_group)
        default_wall_height = self.config.get("takeoff_default_wall_height", "8ft")
        self.takeoff_linear_input = QLineEdit("")
        self.takeoff_height_input = QLineEdit(str(default_wall_height))
        self.takeoff_door_count_input = QLineEdit("0")
        self.takeoff_window_area_input = QLineEdit("0")
        self.takeoff_coats_input = QLineEdit(str(TAKEOFF_DEFAULT_COATS))
        takeoff_layout.addRow("Linear Feet", self.takeoff_linear_input)
        takeoff_layout.addRow("Wall Height", self.takeoff_height_input)
        takeoff_layout.addRow("Door Count", self.takeoff_door_count_input)
        takeoff_layout.addRow("Window Area (sq ft)", self.takeoff_window_area_input)
        takeoff_layout.addRow("Coats", self.takeoff_coats_input)
        layout.addWidget(takeoff_group)

        takeoff_actions = QHBoxLayout()
        estimate_doors_btn = QPushButton("Estimate Doors")
        compute_takeoff_btn = QPushButton("Compute Area")
        compute_takeoff_btn.setObjectName("primaryButton")
        open_measure_tool_btn = QPushButton("Open Click-to-Measure Tool")
        takeoff_actions.addWidget(estimate_doors_btn)
        takeoff_actions.addWidget(compute_takeoff_btn)
        takeoff_actions.addWidget(open_measure_tool_btn)
        takeoff_actions.addStretch(1)
        layout.addLayout(takeoff_actions)

        self.takeoff_result_label = QLabel("Takeoff result will appear here.")
        self.takeoff_result_label.setWordWrap(True)
        layout.addWidget(self.takeoff_result_label)

        invoice_group = QGroupBox("Invoice Builder")
        invoice_layout = QVBoxLayout(invoice_group)
        invoice_layout.addWidget(
            QLabel(
                "Invoice builder is reserved for the next phase.\n"
                "The workspace structure is ready for direct integration."
            )
        )
        layout.addWidget(invoice_group)
        layout.addStretch(1)

        browse_template_btn.clicked.connect(self._browse_quote_template)
        browse_output_btn.clicked.connect(self._browse_quote_output)
        create_quote_btn.clicked.connect(self._create_quote_document)
        open_output_btn.clicked.connect(self._open_quote_output_folder)
        estimate_doors_btn.clicked.connect(self._estimate_takeoff_doors)
        compute_takeoff_btn.clicked.connect(self._compute_takeoff_area)
        open_measure_tool_btn.clicked.connect(self._open_takeoff_tool)
        return tab

    def _restore_window_geometry(self):
        geometry = str(self.config.get("qt_window_geometry", QT_WINDOW_DEFAULT_GEOMETRY))
        try:
            width_text, height_text = geometry.lower().split("x")
            width = max(QT_WINDOW_MIN_WIDTH, int(width_text))
            height = max(QT_WINDOW_MIN_HEIGHT, int(height_text))
        except Exception:
            fallback_width, fallback_height = QT_WINDOW_DEFAULT_GEOMETRY.lower().split("x")
            width = max(QT_WINDOW_MIN_WIDTH, int(fallback_width))
            height = max(QT_WINDOW_MIN_HEIGHT, int(fallback_height))
        self.resize(width, height)

    def closeEvent(self, event):
        self._poll_timer.stop()
        self.config.set("qt_window_geometry", f"{self.width()}x{self.height()}")
        super().closeEvent(event)

    def _set_status(self, text):
        self.status_lbl.setText(text)

    def _navigate_internet(self):
        raw = self.web_url_input.text().strip()
        if not raw:
            return
        if "://" not in raw:
            raw = "https://" + raw
        self.internet_view.setUrl(QUrl(raw))

    def _on_internet_url_changed(self, url):
        self.web_url_input.setText(url.toString())

    def _submit(self, fn, on_result, on_error=None):
        worker = Worker(fn)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._on_worker_error)
        self.thread_pool.start(worker)

    def _on_worker_error(self, trace_text):
        self.connect_btn.setEnabled(True)
        self._set_status("Operation failed")
        QMessageBox.critical(self, "Operation Error", trace_text)

    def _start_authentication(self):
        self.connect_btn.setEnabled(False)
        self._set_status("Authenticating...")
        self._submit(self._auth_worker_task, self._on_authenticated)

    def _reconnect(self):
        self._poll_timer.stop()
        self._poll_in_flight = False
        if self.graph is not None:
            self.graph.clear_cached_tokens()
        else:
            client_id = (self.config.get("client_id") or "").strip() or DEFAULT_CLIENT_ID
            cache_path = token_cache_path_for_client_id(client_id)
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except OSError:
                    pass
        self.graph = None
        self.sync_service = None
        self.current_messages = []
        self.filtered_messages = []
        self.message_cache.clear()
        self.attachment_cache.clear()
        self.cloud_link_cache.clear()
        self.known_ids.clear()
        self.current_message = None
        self.message_list.clear()
        self.attachment_list.clear()
        self.message_header.setText("Disconnected")
        self.email_preview.setHtml("<html><body style='font-family:Segoe UI;'>Reconnect to load mail.</body></html>")
        self.open_cloud_links_btn.setEnabled(False)
        self.cloud_links_info.setText("No linked cloud files found")
        self._set_status("Reconnecting...")
        self._start_authentication()

    def _auth_worker_task(self):
        def on_device_code(flow):
            code = flow.get("user_code", "???")
            self.auth_code_received.emit(code)

        client_id = (self.config.get("client_id") or "").strip() or None
        graph = GraphClient(client_id=client_id, on_device_code=on_device_code)
        if not graph.authenticate():
            raise RuntimeError("Authentication failed.")
        profile = graph.get_profile()
        folders = graph.get_folders()
        return {"graph": graph, "profile": profile, "folders": folders}

    def _show_auth_code_dialog(self, code):
        QMessageBox.information(
            self,
            "Microsoft Sign In",
            "Open microsoft.com/devicelogin and enter this code:\n\n"
            f"{code}\n\n"
            "Finish sign-in in your browser.",
        )

    def _on_authenticated(self, result):
        self.graph = result["graph"]
        self.sync_service = MailSyncService(self.graph, self.cache)
        profile = result.get("profile") or {}
        self.current_user_email = profile.get("mail") or profile.get("userPrincipalName") or ""
        self.connect_btn.setEnabled(True)
        self.setWindowTitle(f"{APP_NAME} - {self.current_user_email}")
        self._set_status(f"Connected as {self.current_user_email}")
        self._populate_folders(result.get("folders") or [])
        self._refresh_company_sidebar()
        self._load_messages()
        self._start_polling()

    def _start_polling(self):
        if not self.sync_service:
            return
        try:
            self.cloud_pdf_cache.prune()
        except Exception as exc:
            print(f"[CLOUD-CACHE] prune error: {exc}")
        self._set_status("Connected. Sync active.")
        self._submit(self._init_delta_token_worker, self._on_delta_token_ready, self._on_poll_error)
        self._poll_timer.start()

    def _init_delta_token_worker(self):
        self.sync_service.initialize_delta_token(folder_id="inbox")
        return True

    def _on_delta_token_ready(self, _):
        self._set_status("Connected. Delta sync ready.")

    def _poll_once(self):
        if not self.sync_service:
            return
        if not self._poll_lock.acquire(blocking=False):
            return
        if self._poll_in_flight:
            self._poll_lock.release()
            return
        self._poll_in_flight = True
        self._submit(self._poll_worker, self._on_poll_result, self._on_poll_error)

    def _poll_worker(self):
        messages, deleted_ids = self.sync_service.sync_delta_once(
            folder_id="inbox",
            fallback_top=EMAIL_DELTA_FALLBACK_TOP,
        )
        return {"messages": messages or [], "deleted_ids": deleted_ids or []}

    def _on_poll_result(self, payload):
        self._poll_in_flight = False
        self._poll_lock.release()

        updates = payload.get("messages") or []
        deleted_ids = payload.get("deleted_ids") or []
        if deleted_ids:
            deleted_set = set(deleted_ids)
            self.current_messages = [msg for msg in self.current_messages if msg.get("id") not in deleted_set]
            self.filtered_messages = [msg for msg in self.filtered_messages if msg.get("id") not in deleted_set]
            for msg_id in deleted_set:
                self.message_cache.pop(msg_id, None)
                self.attachment_cache.pop(msg_id, None)
                self.cloud_link_cache.pop(msg_id, None)
                self.known_ids.discard(msg_id)

        new_unread = collect_new_unread(updates, self.known_ids)
        if updates or deleted_ids:
            index_by_id = {msg.get("id"): idx for idx, msg in enumerate(self.current_messages) if msg.get("id")}
            for msg in updates:
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                idx = index_by_id.get(msg_id)
                if idx is None:
                    self.current_messages.insert(0, msg)
                else:
                    self.current_messages[idx] = msg
            self._render_message_list()
            if self.message_list.count() == 0:
                self.message_header.setText("No messages")
        if new_unread:
            self._set_status(f"{len(new_unread)} new unread message(s)")
        else:
            self._set_status("Connected. Sync up to date.")

    def _on_poll_error(self, trace_text):
        self._poll_in_flight = False
        if self._poll_lock.locked():
            self._poll_lock.release()
        self._set_status("Sync warning. Retrying...")
        print(trace_text)

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

        all_item = QListWidgetItem("All Companies")
        all_item.setData(Qt.UserRole, None)
        self.company_list.addItem(all_item)

        companies_cfg = self.config.get("companies", {}) or {}
        try:
            domain_rows = self.cache.get_all_domains()
        except Exception:
            domain_rows = []

        for row in domain_rows:
            domain = (row.get("domain") or "").lower()
            if not domain:
                continue
            label = row.get("company_label") or companies_cfg.get(domain) or domain_to_company(domain)
            count = row.get("count") or 0
            item = QListWidgetItem(f"{label} · @{domain} ({count})")
            item.setData(Qt.UserRole, domain)
            self.company_list.addItem(item)

        target_index = 0
        if self.company_filter_domain:
            for idx in range(self.company_list.count()):
                item = self.company_list.item(idx)
                if item.data(Qt.UserRole) == self.company_filter_domain:
                    target_index = idx
                    break
        self.company_list.setCurrentRow(target_index)
        self.company_list.blockSignals(False)

    def _on_company_filter_changed(self, row):
        if row < 0:
            return
        item = self.company_list.item(row)
        if item is None:
            return
        self.company_filter_domain = item.data(Qt.UserRole)
        self._render_message_list()
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

    def _on_folder_changed(self, row):
        if row < 0:
            return
        item = self.folder_list.item(row)
        if item is None:
            return
        folder = item.data(Qt.UserRole) or {}
        self.current_folder_id = folder.get("id") or "inbox"
        self._load_messages()

    def _load_messages(self):
        if not self.graph:
            QMessageBox.information(self, "Connect First", "Connect to Microsoft before loading messages.")
            return
        search_text = self.search_input.text().strip() or None
        folder_id = self.current_folder_id
        self._set_status("Loading messages...")
        self._submit(
            lambda: self.graph.get_messages(folder_id=folder_id, top=EMAIL_LIST_FETCH_TOP, search=search_text)[0],
            self._on_messages_loaded,
        )

    def _on_messages_loaded(self, messages):
        self.current_messages = messages or []
        self.known_ids = {msg.get("id") for msg in self.current_messages if msg.get("id")}
        self._refresh_company_sidebar()
        self._render_message_list()
        self._set_status(f"Loaded {len(self.filtered_messages)} of {len(self.current_messages)} messages")
        if self.message_list.count() > 0:
            self.message_list.setCurrentRow(0)
        else:
            self.current_message = None
            self.message_header.setText("No messages")
            self.email_preview.setHtml("<html><body style='font-family:Segoe UI;'>No messages in this folder.</body></html>")
            self.attachment_list.clear()
            self.open_cloud_links_btn.setEnabled(False)
            self.cloud_links_info.setText("No linked cloud files found")

    def _render_message_list(self):
        filtered = []
        domain_filter = (self.company_filter_domain or "").lower()
        for msg in self.current_messages:
            if domain_filter:
                sender = msg.get("from", {}).get("emailAddress", {})
                address = (sender.get("address") or "").lower()
                if "@" not in address:
                    continue
                if address.split("@", 1)[1] != domain_filter:
                    continue
            filtered.append(msg)

        self.filtered_messages = filtered
        self.message_list.clear()
        for msg in self.filtered_messages:
            sender = msg.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
            subject = msg.get("subject") or "(No subject)"
            received = format_date(msg.get("receivedDateTime", ""))
            unread_prefix = "● " if not msg.get("isRead") else ""
            line = f"{unread_prefix}{subject}\n{sender} · {received}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, msg)
            self.message_list.addItem(item)

    def _on_message_selected(self, row):
        if row < 0:
            return
        item = self.message_list.item(row)
        if item is None:
            return
        msg = item.data(Qt.UserRole) or {}
        self.current_message = msg
        message_id = msg.get("id")
        if not message_id:
            return
        self.message_header.setText("Loading message...")
        if message_id in self.message_cache:
            self._render_message_detail(
                self.message_cache[message_id],
                self.attachment_cache.get(message_id, []),
                self.cloud_link_cache.get(message_id, []),
            )
            return
        self._submit(
            lambda: self._fetch_message_detail(message_id),
            self._on_message_detail_loaded,
        )

    def _fetch_message_detail(self, message_id):
        detail = self.graph.get_message(message_id)
        attachments = self.graph.get_attachments(message_id)
        body = detail.get("body", {})
        content_type = (body.get("contentType") or "").lower()
        content = body.get("content") or ""
        plain_text = strip_html(content) if content_type == "html" else (content or detail.get("bodyPreview", ""))
        cloud_links = collect_cloud_pdf_links(content if content_type == "html" else "", plain_text)
        self.cache.save_message_body(message_id, body.get("contentType", ""), body.get("content", ""))
        self.cache.save_attachments(message_id, attachments)
        return {"id": message_id, "detail": detail, "attachments": attachments, "cloud_links": cloud_links}

    def _on_message_detail_loaded(self, payload):
        message_id = payload.get("id")
        detail = payload.get("detail") or {}
        attachments = payload.get("attachments") or []
        cloud_links = payload.get("cloud_links") or []
        if message_id:
            self.message_cache[message_id] = detail
            self.attachment_cache[message_id] = attachments
            self.cloud_link_cache[message_id] = cloud_links
        self._render_message_detail(detail, attachments, cloud_links)

    def _render_message_detail(self, detail, attachments, cloud_links=None):
        sender = detail.get("from", {}).get("emailAddress", {}).get("name") or "Unknown"
        address = detail.get("from", {}).get("emailAddress", {}).get("address") or ""
        received = format_date(detail.get("receivedDateTime", ""))
        subject = detail.get("subject") or "(No subject)"
        self.message_header.setText(f"{subject}\nFrom: {sender} <{address}> · {received}")

        body = detail.get("body", {}) or {}
        content_type = (body.get("contentType") or "").lower()
        content = body.get("content") or ""
        if content_type == "html":
            html_content = ensure_light_preview_html(content)
        else:
            clean_text = strip_html(content) if content else detail.get("bodyPreview", "")
            html_content = wrap_plain_text_as_html(clean_text)
        self.email_preview.setHtml(html_content)

        self.attachment_list.clear()
        for attachment in attachments:
            if attachment.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            name = attachment.get("name") or "attachment"
            size_text = format_size(attachment.get("size") or 0)
            item = QListWidgetItem(f"{name}  ({size_text})")
            item.setData(Qt.UserRole, attachment)
            self.attachment_list.addItem(item)

        cloud_links = cloud_links or []
        self.open_cloud_links_btn.setEnabled(bool(cloud_links))
        if cloud_links:
            sources = sorted({link.get("source", "External") for link in cloud_links})
            summary = ", ".join(sources[:CLOUD_PDF_SOURCE_SUMMARY_MAX]) + (
                "..." if len(sources) > CLOUD_PDF_SOURCE_SUMMARY_MAX else ""
            )
            self.cloud_links_info.setText(f"{len(cloud_links)} linked cloud file(s) detected · {summary}")
        else:
            self.cloud_links_info.setText("No linked cloud files found")

    def _selected_attachment(self):
        item = self.attachment_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _download_attachment_bytes(self, message_id, attachment_id):
        attachment = self.graph.download_attachment(message_id, attachment_id)
        encoded = attachment.get("contentBytes")
        if not encoded:
            raise RuntimeError("Attachment payload did not include content bytes.")
        return base64.b64decode(encoded), attachment.get("name") or "attachment.bin"

    def _open_selected_attachment(self):
        attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Select Attachment", "Select an attachment first.")
            return
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            return
        self._set_status("Downloading attachment...")
        self._submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            self._on_open_attachment_ready,
        )

    def _on_open_attachment_ready(self, payload):
        payload_bytes, filename = payload
        os.makedirs(PDF_DIR, exist_ok=True)
        target_path = self._unique_output_path(PDF_DIR, filename)
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        if target_path.lower().endswith(".pdf"):
            self._open_pdf_file(target_path, activate=True)
        else:
            open_document_file(target_path)
        self._set_status(f"Opened attachment: {os.path.basename(target_path)}")

    def _save_selected_attachment(self):
        attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Select Attachment", "Select an attachment first.")
            return
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            return
        default_name = attachment.get("name") or "attachment.bin"
        target_path, _ = QFileDialog.getSaveFileName(self, "Save Attachment", default_name)
        if not target_path:
            return
        self._set_status("Saving attachment...")
        self._submit(
            lambda: self._download_attachment_bytes(message_id, attachment.get("id")),
            partial(self._on_save_attachment_ready, target_path=target_path),
        )

    def _on_save_attachment_ready(self, payload, target_path):
        payload_bytes, _ = payload
        with open(target_path, "wb") as handle:
            handle.write(payload_bytes)
        self._set_status(f"Saved attachment: {os.path.basename(target_path)}")

    def _open_cloud_links_for_current(self):
        message_id = (self.current_message or {}).get("id")
        if not message_id:
            QMessageBox.information(self, "No Message", "Select a message first.")
            return
        links = self.cloud_link_cache.get(message_id) or []
        if not links:
            QMessageBox.information(self, "No Links", "No supported cloud PDF links found in this email.")
            return

        if len(links) == 1:
            selected_links = links
        else:
            dialog = CloudPdfLinkDialog(self, links)
            if dialog.exec() != QDialog.Accepted:
                return
            selected_links = dialog.selected_links()
            if not selected_links:
                return

        self._set_status(f"Opening {len(selected_links)} linked PDF(s)...")
        self._submit(
            lambda: self._download_cloud_links(selected_links),
            self._on_cloud_links_downloaded,
        )

    def _download_cloud_links(self, selected_links):
        opened_items = []
        failures = []
        for index, link in enumerate(selected_links, start=1):
            try:
                source = link.get("source", "External")
                suggested = link.get("suggested_name") or f"linked_{index}.pdf"
                result = self.cloud_pdf_cache.acquire_pdf(
                    link.get("download_url", ""),
                    suggested_name=suggested,
                    source=source,
                )
                opened_items.append({"path": result.path, "from_cache": result.from_cache})
            except (BrowserDownloadError, OSError, ValueError) as exc:
                failures.append(f"{link.get('source', 'External')}: {exc}")
        return {"opened_items": opened_items, "failures": failures}

    def _on_cloud_links_downloaded(self, payload):
        opened_items = payload.get("opened_items") or []
        failures = payload.get("failures") or []
        cache_hits = 0

        for idx, item in enumerate(opened_items):
            path = item.get("path")
            if not path:
                continue
            if item.get("from_cache"):
                cache_hits += 1
            self._open_pdf_file(path, activate=(idx == 0))

        if opened_items:
            self.workspace_tabs.setCurrentWidget(self.pdf_tab)
            if cache_hits:
                self._set_status(f"Opened {len(opened_items)} linked PDF(s) · {cache_hits} from cache")
            else:
                self._set_status(f"Opened {len(opened_items)} linked PDF(s)")
        else:
            self._set_status("No linked PDFs opened")

        if failures:
            QMessageBox.warning(
                self,
                "Some Links Failed",
                "Could not open all selected links:\n\n"
                + "\n".join(failures[:CLOUD_PDF_FAILURE_PREVIEW_MAX]),
            )

    def _open_compose_dialog(self, mode):
        if mode != "new" and not self.current_message:
            QMessageBox.information(self, "Select Message", "Select a message first.")
            return
        defaults = self._compose_defaults(mode)
        mode_label = {
            "new": "New Email",
            "reply": "Reply",
            "reply_all": "Reply All",
            "forward": "Forward",
        }.get(mode, "Compose")
        dialog = ComposeDialog(self, mode_label, defaults, self._start_send_from_dialog)
        dialog.exec()

    def _compose_defaults(self, mode):
        if mode == "new" or not self.current_message:
            return {"to": "", "cc": "", "subject": "", "body": ""}
        detail = self.message_cache.get(self.current_message.get("id"), self.current_message)
        subject = detail.get("subject") or ""
        sender_name = detail.get("from", {}).get("emailAddress", {}).get("name") or ""
        sender_addr = detail.get("from", {}).get("emailAddress", {}).get("address") or ""
        date_text = detail.get("receivedDateTime", "")
        body = detail.get("body", {}).get("content") or detail.get("bodyPreview") or ""
        if detail.get("body", {}).get("contentType", "").lower() == "html":
            body = strip_html(body)
        quoted = (
            "\n\n"
            f"--- Original message ---\n"
            f"From: {sender_name} <{sender_addr}>\n"
            f"Date: {date_text}\n"
            f"Subject: {subject}\n\n"
            f"{body}"
        )

        if mode == "forward":
            return {"to": "", "cc": "", "subject": f"FW: {subject}", "body": quoted}

        include_all = mode == "reply_all"
        to_list, cc_list = build_reply_recipients(
            detail,
            current_user_email=self.current_user_email,
            include_all=include_all,
        )
        return {
            "to": "; ".join(to_list),
            "cc": "; ".join(cc_list),
            "subject": f"RE: {subject}",
            "body": quoted,
        }

    def _start_send_from_dialog(self, payload, dialog):
        if not self.graph:
            dialog.mark_send_failed("Not connected.")
            return
        self._set_status("Sending email...")
        self._submit(
            lambda: self._send_mail_worker(payload),
            lambda _: self._on_send_completed(dialog),
            lambda err: dialog.mark_send_failed(err),
        )

    def _send_mail_worker(self, payload):
        self.graph.send_mail(
            payload["to"],
            payload["cc"],
            payload["subject"],
            payload["body"],
            attachments=payload["attachments"],
        )
        return True

    def _on_send_completed(self, dialog):
        self._set_status("Email sent")
        QMessageBox.information(self, "Sent", "Email sent successfully.")
        dialog.accept()

    def _open_pdf_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", PDF_DIR, "PDF Files (*.pdf);;All Files (*.*)")
        if not path:
            return
        self._open_pdf_file(path, activate=True)

    def _open_pdf_file(self, path, activate=False):
        normalized = os.path.abspath(path)
        if not os.path.isfile(normalized):
            QMessageBox.warning(self, "PDF Not Found", f"Could not find PDF:\n{normalized}")
            return
        existing_index = self._find_pdf_tab_index(normalized)
        if existing_index is not None:
            self.pdf_tabs.setCurrentIndex(existing_index)
            if activate:
                self.workspace_tabs.setCurrentWidget(self.pdf_tab)
            return

        for idx in reversed(range(self.pdf_tabs.count())):
            widget = self.pdf_tabs.widget(idx)
            if widget is not None and widget.property("is_placeholder"):
                self.pdf_tabs.removeTab(idx)
                widget.deleteLater()

        try:
            view = self._create_pdf_widget(normalized)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Load Error", f"Could not open PDF:\n{normalized}\n\n{exc}")
            return

        view.setProperty("pdf_path", normalized.lower())
        tab_label = os.path.basename(normalized)
        self.pdf_tabs.addTab(view, tab_label)
        self.pdf_tabs.setCurrentWidget(view)
        if activate:
            self.workspace_tabs.setCurrentWidget(self.pdf_tab)
        self._set_status(f"Opened PDF: {tab_label}")

    def _create_pdf_widget(self, normalized_path):
        errors = []
        if HAS_QTPDF:
            try:
                return self._create_qtpdf_widget(normalized_path)
            except Exception as exc:
                errors.append(f"QtPdf: {exc}")

        try:
            return self._create_webengine_pdf_widget(normalized_path)
        except Exception as exc:
            errors.append(f"WebEngine: {exc}")

        detail = "; ".join(errors) if errors else "No PDF renderer available."
        raise RuntimeError(detail)

    def _create_qtpdf_widget(self, normalized_path):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        document = QPdfDocument(container)
        load_error = document.load(normalized_path)
        if load_error != QPdfDocument.Error.None_:
            raise RuntimeError(f"QtPdf load failed: {load_error.name}")

        view = QPdfView(container)
        view.setDocument(document)
        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(view, 1)

        container._pdf_document = document
        container._pdf_view = view
        return container

    def _create_webengine_pdf_widget(self, normalized_path):
        view = QWebEngineView()
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        view.setUrl(QUrl.fromLocalFile(normalized_path))
        return view

    def _find_pdf_tab_index(self, path):
        normalized = path.lower()
        for idx in range(self.pdf_tabs.count()):
            widget = self.pdf_tabs.widget(idx)
            if widget is None:
                continue
            if widget.property("pdf_path") == normalized:
                return idx
        return None

    def _on_pdf_tab_close_requested(self, index):
        widget = self.pdf_tabs.widget(index)
        if widget is not None:
            self.pdf_tabs.removeTab(index)
            widget.deleteLater()
        if self.pdf_tabs.count() == 0:
            self._add_pdf_placeholder_tab()

    def _close_current_pdf_tab(self):
        idx = self.pdf_tabs.currentIndex()
        if idx >= 0:
            self._on_pdf_tab_close_requested(idx)

    def _add_pdf_placeholder_tab(self):
        placeholder = QLabel("Open a PDF to view it here.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setProperty("is_placeholder", True)
        self.pdf_tabs.addTab(placeholder, "Current PDF")

    def _browse_quote_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Quote Template",
            self.quote_template_input.text().strip() or DEFAULT_QUOTE_TEMPLATE_FILE,
            "Word/Text Templates (*.doc *.docx *.txt);;All Files (*.*)",
        )
        if not path:
            return
        self.quote_template_input.setText(path)
        self.config.set("quote_template_path", path)

    def _browse_quote_output(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Quote Output Folder",
            self.quote_output_input.text().strip() or QUOTE_DIR,
        )
        if not path:
            return
        self.quote_output_input.setText(path)
        self.config.set("quote_output_dir", path)

    def _create_quote_document(self):
        template_path = self.quote_template_input.text().strip() or DEFAULT_QUOTE_TEMPLATE_FILE
        output_dir = self.quote_output_input.text().strip() or QUOTE_DIR
        context = build_quote_context(
            to_value=self.quote_email_input.text().strip(),
            subject_value=self.quote_project_input.text().strip(),
        )
        if self.quote_client_input.text().strip():
            context["client_name"] = self.quote_client_input.text().strip()
        if self.quote_reference_input.text().strip():
            context["email_subject"] = self.quote_reference_input.text().strip()
        try:
            quote_path = create_quote_doc(template_path, output_dir, context)
        except Exception as exc:
            QMessageBox.critical(self, "Quote Error", str(exc))
            return

        self._set_status(f"Quote created: {os.path.basename(quote_path)}")
        opened = open_document_file(quote_path)
        if not opened:
            QMessageBox.information(self, "Quote Created", f"Quote created at:\n{quote_path}")

    def _open_quote_output_folder(self):
        folder = self.quote_output_input.text().strip() or QUOTE_DIR
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _estimate_takeoff_doors(self):
        linear_raw = self.takeoff_linear_input.text().strip()
        if not linear_raw:
            QMessageBox.information(self, "Linear Feet Needed", "Enter linear feet before estimating doors.")
            return
        try:
            linear_feet = parse_length_to_feet(linear_raw, default_unit="ft")
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Linear Feet", str(exc))
            return
        estimate = estimate_door_count(linear_feet)
        self.takeoff_door_count_input.setText(str(estimate))
        self._set_status(f"Door estimate set to {estimate}")

    def _compute_takeoff_area(self):
        linear_raw = self.takeoff_linear_input.text().strip()
        height_raw = self.takeoff_height_input.text().strip()
        door_count_raw = self.takeoff_door_count_input.text().strip() or "0"
        window_area_raw = self.takeoff_window_area_input.text().strip() or "0"
        coats_raw = self.takeoff_coats_input.text().strip() or str(TAKEOFF_DEFAULT_COATS)

        if not linear_raw or not height_raw:
            QMessageBox.information(self, "Missing Inputs", "Provide linear feet and wall height.")
            return

        try:
            linear_feet = parse_length_to_feet(linear_raw, default_unit="ft")
            wall_height = parse_length_to_feet(height_raw, default_unit="ft")
            door_count = int(door_count_raw)
            window_area_sqft = float(window_area_raw)
            coats = int(coats_raw)
            result = compute_takeoff(
                linear_feet=linear_feet,
                wall_height_feet=wall_height,
                door_count=door_count,
                window_area_sqft=window_area_sqft,
                coats=coats,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Takeoff Error", str(exc))
            return

        self.config.set("takeoff_default_wall_height", height_raw)
        self.takeoff_result_label.setText(
            f"Gross: {result.gross_area_sqft:.1f} sq ft · "
            f"Openings: {result.opening_area_sqft:.1f} sq ft · "
            f"Net: {result.net_area_sqft:.1f} sq ft · "
            f"Paint Area ({result.coats} coat(s)): {result.paint_area_sqft:.1f} sq ft"
        )
        self._set_status("Takeoff area computed")

    def _open_takeoff_tool(self):
        takeoff_script = os.path.join(ROOT_DIR, "pdf_takeoff_tool.py")
        if not os.path.isfile(takeoff_script):
            QMessageBox.warning(self, "Takeoff Tool Missing", f"Could not find takeoff tool:\n{takeoff_script}")
            return
        try:
            subprocess.Popen([sys.executable, takeoff_script], cwd=ROOT_DIR)
            self._set_status("Takeoff tool opened")
        except Exception as exc:
            QMessageBox.critical(self, "Takeoff Launch Failed", str(exc))

    def _launch_scanner(self):
        scanner_script = os.path.join(ROOT_DIR, "scanner_app_v4.py")
        if not os.path.isfile(scanner_script):
            QMessageBox.warning(self, "Scanner Missing", f"Could not find scanner script:\n{scanner_script}")
            return
        try:
            subprocess.Popen([sys.executable, scanner_script], cwd=ROOT_DIR)
            self._set_status("Scanner opened")
        except Exception as exc:
            QMessageBox.critical(self, "Scanner Launch Failed", str(exc))

    @staticmethod
    def _unique_output_path(directory, filename):
        safe_name = os.path.basename(filename or "download.bin")
        base, ext = os.path.splitext(safe_name)
        candidate = os.path.join(directory, safe_name)
        index = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{index}{ext}")
            index += 1
        return candidate
