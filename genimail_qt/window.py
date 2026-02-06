import threading

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QMainWindow

from genimail.constants import POLL_INTERVAL_MS, QT_THREAD_POOL_MAX_WORKERS
from genimail.infra.cache_store import EmailCache
from genimail.infra.config_store import Config
from genimail_qt.helpers import Toaster, WorkerManager
from genimail_qt.mixins import (
    AuthPollMixin,
    CompanyMixin,
    CompanySearchMixin,
    ComposeMixin,
    DocsMixin,
    EmailAttachmentMixin,
    EmailListMixin,
    EmailUiMixin,
    InternetMixin,
    LayoutMixin,
    PdfMixin,
    PdfUiMixin,
    WindowStateMixin,
)
from genimail_qt.mixins.pdf import HAS_QTPDF


class GeniMailQtWindow(
    LayoutMixin,
    InternetMixin,
    EmailUiMixin,
    PdfUiMixin,
    DocsMixin,
    WindowStateMixin,
    AuthPollMixin,
    CompanyMixin,
    CompanySearchMixin,
    EmailListMixin,
    EmailAttachmentMixin,
    ComposeMixin,
    PdfMixin,
    QMainWindow,
):
    auth_code_received = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.cache = EmailCache()
        self.graph = None
        self.sync_service = None
        self.current_user_email = ""
        self.current_folder_id = "inbox"
        self.current_messages = []
        self.filtered_messages = []
        self.current_message = None
        self.message_cache = {}
        self.attachment_cache = {}
        self.known_ids = set()
        self.company_filter_domain = None
        self.company_domain_labels = {}
        self.company_result_messages = []
        self.company_folder_filter = "all"
        self.company_folder_sources = []
        self.company_query_cache = {}
        self.company_query_inflight = set()
        self._company_load_token = 0
        self._web_page_sources = {}
        self._download_profile_ids = set()
        self._poll_in_flight = False
        self._poll_lock = threading.Lock()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(QT_THREAD_POOL_MAX_WORKERS)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_once)
        self.toaster = Toaster(self, lambda: self._top_bar.height() if hasattr(self, "_top_bar") else 0)
        self.workers = WorkerManager(self.thread_pool, self, self._on_default_worker_error)

        self._build_ui()
        self._restore_window_geometry()
        self.auth_code_received.connect(self._show_auth_code_dialog)
        QTimer.singleShot(250, self._auto_connect_on_startup)

    def _on_default_worker_error(self, _trace_text):
        self.connect_btn.setEnabled(True)
        self._set_status("Operation failed")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toaster.reposition()
        if hasattr(self, "_on_host_geometry_changed"):
            self._on_host_geometry_changed()

    def eventFilter(self, obj, event):
        if self.toaster.event_filter(obj, event):
            return True
        return super().eventFilter(obj, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "_on_host_geometry_changed"):
            self._on_host_geometry_changed()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.WindowStateChange:
            return

        if self.isMinimized():
            if hasattr(self, "_minimize_external_browser"):
                self._minimize_external_browser()
            return

        if hasattr(self, "_on_host_geometry_changed"):
            self._on_host_geometry_changed()


__all__ = ["GeniMailQtWindow", "HAS_QTPDF"]
