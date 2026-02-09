from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from genimail.constants import QT_SPLITTER_LEFT_DEFAULT, QT_SPLITTER_RIGHT_DEFAULT
from genimail_qt.constants import ATTACHMENT_THUMBNAIL_HEIGHT_PX


class EmailUiMixin:
    def _build_email_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search emails...")
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primaryButton")
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_btn)
        self._search_completer = QCompleter(self)
        self._search_completer.setModel(QStringListModel([], self))
        self._search_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._search_completer.setFilterMode(Qt.MatchContains)
        self._search_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.search_input.setCompleter(self._search_completer)
        left_layout.addLayout(search_row)
        left_layout.addWidget(QLabel("Folders"))
        self.folder_buttons_widget = QWidget()
        self.folder_buttons_widget.setObjectName("folderButtonsWidget")
        self.folder_buttons_layout = QVBoxLayout(self.folder_buttons_widget)
        self.folder_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_buttons_layout.setSpacing(6)
        left_layout.addWidget(self.folder_buttons_widget, 0)
        left_layout.addStretch(1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)

        company_row = QHBoxLayout()
        company_row.setSpacing(8)
        self.company_tabs_scroll = QScrollArea()
        self.company_tabs_scroll.setObjectName("companyTabsScroll")
        self.company_tabs_scroll.setWidgetResizable(True)
        self.company_tabs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.company_tabs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.company_tabs_scroll.setFrameShape(QFrame.NoFrame)
        self.company_tabs_widget = QWidget()
        self.company_tabs_widget.setObjectName("companyTabsContainer")
        self.company_tabs_layout = QHBoxLayout(self.company_tabs_widget)
        self.company_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.company_tabs_layout.setSpacing(6)
        self.company_tabs_scroll.setWidget(self.company_tabs_widget)
        company_row.addWidget(self.company_tabs_scroll, 1)

        self.manage_companies_btn = QPushButton("Manage Companies")
        self.manage_companies_btn.setObjectName("companyInlineButton")
        company_row.addWidget(self.manage_companies_btn)
        right_layout.addLayout(company_row)

        self.company_folder_filter_widget = QWidget()
        self.company_folder_filter_widget.setObjectName("companyFolderFilterWidget")
        self.company_folder_filter_layout = QHBoxLayout(self.company_folder_filter_widget)
        self.company_folder_filter_layout.setContentsMargins(0, 0, 0, 0)
        self.company_folder_filter_layout.setSpacing(6)
        right_layout.addWidget(self.company_folder_filter_widget)
        self.company_folder_filter_widget.hide()

        company_filter_row = QHBoxLayout()
        self.company_filter_badge = QLabel("")
        self.company_filter_badge.setObjectName("companyFilterBadge")
        company_filter_row.addWidget(self.company_filter_badge, 1)
        self.clear_company_filter_btn = QPushButton("Clear")
        self.clear_company_filter_btn.setObjectName("companyInlineButton")
        company_filter_row.addWidget(self.clear_company_filter_btn)
        right_layout.addLayout(company_filter_row)

        self.message_stack = QStackedWidget()

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(6)
        list_layout.addWidget(QLabel("Messages"))
        self.message_list = QListWidget()
        self.message_list.setObjectName("messageList")
        self.message_list.setAlternatingRowColors(False)
        list_layout.addWidget(self.message_list, 1)
        self.message_stack.addWidget(list_page)

        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)
        detail_layout.setContentsMargins(4, 4, 4, 4)
        detail_layout.setSpacing(8)

        back_row = QHBoxLayout()
        self.back_to_list_btn = QPushButton("Back to list")
        self.back_to_list_btn.setObjectName("backToListBtn")
        back_row.addWidget(self.back_to_list_btn)
        back_row.addStretch(1)
        detail_layout.addLayout(back_row)

        attach_box = QGroupBox("Attachments")
        attach_layout = QVBoxLayout(attach_box)
        self.attach_container = self._build_attachment_thumbnails()
        attach_layout.addWidget(self.attach_container)
        self.attachment_list = QListWidget()
        self.attachment_list.hide()
        attach_layout.addWidget(self.attachment_list)
        attach_buttons = QHBoxLayout()
        self.open_attachment_btn = QPushButton("Open Selected")
        self.save_attachment_btn = QPushButton("Save Selected As...")
        attach_buttons.addWidget(self.open_attachment_btn)
        attach_buttons.addWidget(self.save_attachment_btn)
        attach_buttons.addStretch(1)
        attach_layout.addLayout(attach_buttons)
        self.download_results_widget = QWidget()
        self.download_results_layout = QHBoxLayout(self.download_results_widget)
        self.download_results_layout.setContentsMargins(0, 0, 0, 0)
        self.download_results_layout.setSpacing(6)
        self.download_results_layout.addStretch(1)
        self.download_results_widget.hide()
        attach_layout.addWidget(self.download_results_widget)
        detail_layout.addWidget(attach_box)

        self.message_header = QLabel("Select a message")
        self.message_header.setObjectName("messageHeader")
        detail_layout.addWidget(self.message_header)

        self.email_preview = self._create_web_view("email")
        preview_settings = self.email_preview.settings()
        preview_settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        preview_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        preview_settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.email_preview.setHtml("<html><body style='font-family:Segoe UI;'>No message selected.</body></html>")
        detail_layout.addWidget(self.email_preview, 1)

        self.message_stack.addWidget(detail_page)
        right_layout.addWidget(self.message_stack, 1)

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
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([QT_SPLITTER_LEFT_DEFAULT, QT_SPLITTER_RIGHT_DEFAULT])

        self.clear_company_filter_btn.clicked.connect(self._clear_company_filter)
        self.manage_companies_btn.clicked.connect(self._open_company_manager)
        self.search_btn.clicked.connect(self._load_messages)
        self.search_input.returnPressed.connect(self._load_messages)
        self.message_list.currentRowChanged.connect(self._on_message_row_changed)
        self.message_list.itemActivated.connect(self._on_message_opened)
        self.back_to_list_btn.clicked.connect(self._show_message_list)
        self.open_attachment_btn.clicked.connect(self._open_selected_attachment)
        self.save_attachment_btn.clicked.connect(self._save_selected_attachment)
        self.new_mail_btn.clicked.connect(lambda: self._open_compose_dialog("new"))
        self.reply_btn.clicked.connect(lambda: self._open_compose_dialog("reply"))
        self.reply_all_btn.clicked.connect(lambda: self._open_compose_dialog("reply_all"))
        self.forward_btn.clicked.connect(lambda: self._open_compose_dialog("forward"))
        self._refresh_company_sidebar()
        self._show_message_list()
        if hasattr(self, "_load_search_history"):
            self._load_search_history()
        return tab

    def _build_attachment_thumbnails(self):
        container = QWidget()
        container.setObjectName("attachmentThumbnails")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(ATTACHMENT_THUMBNAIL_HEIGHT_PX)

        inner = QWidget()
        self.thumbnail_layout = QHBoxLayout(inner)
        self.thumbnail_layout.setContentsMargins(8, 8, 8, 8)
        self.thumbnail_layout.setSpacing(8)
        self.thumbnail_layout.addStretch(1)

        scroll.setWidget(inner)
        container_layout.addWidget(scroll)
        container.hide()
        return container

    def _show_message_list(self):
        if not hasattr(self, "message_stack"):
            return
        self.message_stack.setCurrentIndex(0)
        if hasattr(self, "_list_scroll_pos"):
            self.message_list.verticalScrollBar().setValue(self._list_scroll_pos)

    def _show_message_detail(self):
        if not hasattr(self, "message_stack"):
            return
        self._list_scroll_pos = self.message_list.verticalScrollBar().value()
        self.message_stack.setCurrentIndex(1)


__all__ = ["EmailUiMixin"]
