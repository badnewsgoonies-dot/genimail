import threading

from PySide6.QtCore import QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QMainWindow

from genimail.constants import POLL_INTERVAL_MS, QT_THREAD_POOL_MAX_WORKERS
from genimail.infra.cache_store import EmailCache
from genimail.infra.config_store import Config
from genimail_qt.cloud_pdf_cache import CloudPdfCache
from genimail_qt.mixins import (
    AuthPollMixin,
    CompanyMixin,
    ComposeMixin,
    DocsMixin,
    EmailAttachmentMixin,
    EmailListMixin,
    EmailUiMixin,
    InternetMixin,
    LayoutMixin,
    PdfMixin,
    PdfUiMixin,
    ToastMixin,
    WindowStateMixin,
    WorkerMixin,
)
from genimail_qt.mixins.pdf import HAS_QTPDF


class GeniMailQtWindow(
    ToastMixin,
    LayoutMixin,
    InternetMixin,
    EmailUiMixin,
    PdfUiMixin,
    DocsMixin,
    WindowStateMixin,
    WorkerMixin,
    AuthPollMixin,
    CompanyMixin,
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
        self.cloud_pdf_downloads = {}
        self.known_ids = set()
        self.company_filter_domain = None
        self.company_domain_labels = {}
        self._web_page_sources = {}
        self._download_profile_ids = set()
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


__all__ = ["GeniMailQtWindow", "HAS_QTPDF"]
