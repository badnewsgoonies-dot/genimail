from PySide6.QtCore import Qt
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from genimail.constants import QT_SPLITTER_LEFT_DEFAULT, QT_SPLITTER_RIGHT_DEFAULT
from genimail_qt.constants import COMPANY_STAR_ICON


class EmailUiMixin:
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
        self.company_section_btn = QPushButton()
        self.company_section_btn.setObjectName("companySectionButton")
        self.company_section_btn.setCheckable(True)
        company_header.addWidget(self.company_section_btn, 1)
        self.manage_companies_btn = QPushButton("Manage")
        self.manage_companies_btn.setObjectName("companyInlineButton")
        company_header.addWidget(self.manage_companies_btn)
        left_layout.addLayout(company_header)

        company_filter_row = QHBoxLayout()
        self.company_filter_badge = QLabel("")
        self.company_filter_badge.setObjectName("companyFilterBadge")
        company_filter_row.addWidget(self.company_filter_badge, 1)
        self.clear_company_filter_btn = QPushButton("Clear")
        self.clear_company_filter_btn.setObjectName("companyInlineButton")
        company_filter_row.addWidget(self.clear_company_filter_btn)
        left_layout.addLayout(company_filter_row)

        self.company_body = QWidget()
        company_body_layout = QVBoxLayout(self.company_body)
        company_body_layout.setContentsMargins(0, 0, 0, 0)
        company_body_layout.setSpacing(6)
        self.company_list = QListWidget()
        self.company_list.setObjectName("companyList")
        company_body_layout.addWidget(self.company_list, 1)
        company_actions = QHBoxLayout()
        self.company_favorite_btn = QPushButton(f"{COMPANY_STAR_ICON} Favorite")
        self.company_favorite_btn.setObjectName("companyInlineButton")
        self.company_hide_btn = QPushButton("Hide")
        self.company_hide_btn.setObjectName("companyInlineButton")
        self.company_color_btn = QPushButton("Color")
        self.company_color_btn.setObjectName("companyInlineButton")
        company_actions.addWidget(self.company_favorite_btn)
        company_actions.addWidget(self.company_hide_btn)
        company_actions.addWidget(self.company_color_btn)
        company_body_layout.addLayout(company_actions)
        left_layout.addWidget(self.company_body, 1)

        left_layout.addWidget(QLabel("Messages"))
        self.message_list = QListWidget()
        left_layout.addWidget(self.message_list, 2)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.message_header = QLabel("Select a message")
        right_layout.addWidget(self.message_header)

        self.email_preview = self._create_web_view("email")
        preview_settings = self.email_preview.settings()
        preview_settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        preview_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        preview_settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.email_preview.setHtml("<html><body style='font-family:Segoe UI;'>No message selected.</body></html>")
        right_layout.addWidget(self.email_preview, 1)

        attach_box = QGroupBox("Attachments")
        attach_layout = QVBoxLayout(attach_box)
        self.attachment_list = QListWidget()
        attach_layout.addWidget(self.attachment_list, 1)
        self.cloud_links_info = QLabel("No linked cloud files found")
        attach_layout.addWidget(self.cloud_links_info)
        self.cloud_download_label = QLabel("Downloaded PDFs")
        self.cloud_download_label.setObjectName("companyFilterBadge")
        attach_layout.addWidget(self.cloud_download_label)
        self.cloud_download_list = QListWidget()
        attach_layout.addWidget(self.cloud_download_list, 1)
        self.cloud_download_label.hide()
        self.cloud_download_list.hide()
        attach_buttons = QHBoxLayout()
        self.open_attachment_btn = QPushButton("Open Selected")
        self.save_attachment_btn = QPushButton("Save Selected As...")
        self.open_cloud_links_btn = QPushButton("Open Linked PDFs")
        self.open_cloud_download_btn = QPushButton("Open Downloaded")
        self.open_cloud_links_btn.setEnabled(False)
        self.open_cloud_download_btn.setEnabled(False)
        attach_buttons.addWidget(self.open_attachment_btn)
        attach_buttons.addWidget(self.save_attachment_btn)
        attach_buttons.addWidget(self.open_cloud_links_btn)
        attach_buttons.addWidget(self.open_cloud_download_btn)
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
        self.company_list.itemClicked.connect(self._on_company_item_clicked)
        self.company_section_btn.clicked.connect(self._toggle_company_section_from_button)
        self.clear_company_filter_btn.clicked.connect(self._clear_company_filter)
        self.company_favorite_btn.clicked.connect(self._toggle_selected_company_favorite)
        self.company_hide_btn.clicked.connect(self._toggle_selected_company_hidden)
        self.company_color_btn.clicked.connect(self._pick_selected_company_color)
        self.manage_companies_btn.clicked.connect(self._open_company_manager)
        self.search_btn.clicked.connect(self._load_messages)
        self.search_input.returnPressed.connect(self._load_messages)
        self.message_list.currentRowChanged.connect(self._on_message_selected)
        self.open_attachment_btn.clicked.connect(self._open_selected_attachment)
        self.save_attachment_btn.clicked.connect(self._save_selected_attachment)
        self.open_cloud_links_btn.clicked.connect(self._open_cloud_links_for_current)
        self.open_cloud_download_btn.clicked.connect(self._open_selected_cloud_download)
        self.cloud_download_list.currentRowChanged.connect(self._update_cloud_download_buttons)
        self.new_mail_btn.clicked.connect(lambda: self._open_compose_dialog("new"))
        self.reply_btn.clicked.connect(lambda: self._open_compose_dialog("reply"))
        self.reply_all_btn.clicked.connect(lambda: self._open_compose_dialog("reply_all"))
        self.forward_btn.clicked.connect(lambda: self._open_compose_dialog("forward"))
        self._refresh_company_sidebar()
        self._set_company_collapsed(bool(self.config.get("company_collapsed", False)), persist=False)
        return tab


__all__ = ["EmailUiMixin"]
