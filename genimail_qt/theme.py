APP_STYLE = """
QWidget {
    font-size: 13px;
}
QMainWindow {
    background-color: #f5f6f8;
}
QFrame#topBar {
    background-color: #fdfdfd;
    border-bottom: 1px solid #dfe3ea;
}
QLabel#appTitle {
    color: #1b1f24;
    font-size: 20px;
    font-weight: 700;
}
QLabel#statusLabel {
    color: #586171;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #dfe3ea;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: #f3f5f8;
    border: 1px solid #dfe3ea;
    border-bottom-color: #dfe3ea;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    min-width: 136px;
    min-height: 36px;
    padding: 8px 14px;
    color: #4a5565;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0f172a;
    border-bottom-color: #ffffff;
    font-weight: 600;
}
QPushButton {
    background: #f3f5f8;
    border: 1px solid #cfd5df;
    border-radius: 6px;
    color: #1f2937;
    padding: 8px 12px;
    min-height: 32px;
}
QPushButton:hover {
    border-color: #9db2d0;
    background: #eef3fb;
}
QPushButton:disabled {
    color: #98a2b3;
    background: #f7f8fa;
    border-color: #e5e7eb;
}
QPushButton#primaryButton {
    background: #1f6feb;
    border-color: #1f6feb;
    color: white;
}
QPushButton#primaryButton:hover {
    background: #185fc9;
    border-color: #185fc9;
}
QPushButton#companySectionButton {
    text-align: left;
    font-weight: 600;
    background: #eef2f8;
    border-color: #cfd5df;
}
QPushButton#companySectionButton:hover {
    background: #e7edf7;
}
QPushButton#companyInlineButton {
    padding: 4px 8px;
    min-height: 24px;
    background: #f9fafb;
}
QPushButton#companyInlineButton:hover {
    background: #eff4fc;
    border-color: #9db2d0;
}
QScrollArea#companyTabsScroll {
    background: transparent;
}
QWidget#companyTabsContainer {
    background: transparent;
}
QPushButton#companyTabButton {
    background: #f5f7fb;
    border: 1px solid #d7deea;
    border-radius: 999px;
    color: #334155;
    padding: 6px 12px;
    min-height: 28px;
}
QPushButton#companyTabButton:hover {
    background: #eef4ff;
    border-color: #9db2d0;
}
QPushButton#companyTabButton:checked {
    background: #e8f0ff;
    border-color: #7ea6e8;
    color: #0f3d86;
    font-weight: 600;
}
QWidget#companyFolderFilterWidget {
    background: transparent;
}
QPushButton#companyFolderChip {
    background: #f8fafc;
    border: 1px solid #d7deea;
    border-radius: 999px;
    color: #475467;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton#companyFolderChip:hover {
    background: #f1f5ff;
    border-color: #9db2d0;
}
QPushButton#companyFolderChip:checked {
    background: #e8f0ff;
    border-color: #7ea6e8;
    color: #0f3d86;
    font-weight: 600;
}
QPushButton#backToListBtn {
    background: transparent;
    border: none;
    color: #1f6feb;
    font-weight: 600;
    padding: 4px 8px;
}
QPushButton#backToListBtn:hover {
    text-decoration: underline;
    background: transparent;
    border: none;
}
QLabel#companyFilterBadge {
    background: #edf5ff;
    border: 1px solid #c7dcff;
    border-radius: 6px;
    color: #1f4b8e;
    padding: 6px 10px;
    font-size: 13px;
}
QLabel#messageHeader {
    color: #1f2937;
    font-size: 14px;
    font-weight: 600;
    padding: 2px 0 4px 0;
}
QFrame#toastFrame {
    background: #1f2937;
    border-radius: 8px;
    border: 1px solid #2b3648;
}
QFrame#toastFrame[toastKind="success"] {
    background: #1f6feb;
    border-color: #1f6feb;
}
QFrame#toastFrame[toastKind="error"] {
    background: #b42318;
    border-color: #b42318;
}
QLabel#toastLabel {
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
}
QLineEdit, QTextEdit, QListWidget {
    border: 1px solid #d2d8e2;
    border-radius: 6px;
    background: #ffffff;
    color: #0f172a;
    font-size: 13px;
}
QLineEdit, QTextEdit {
    padding: 8px 10px;
    min-height: 34px;
}
QGroupBox {
    border: 1px solid #dfe3ea;
    border-radius: 8px;
    margin-top: 12px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #475467;
    font-weight: 600;
    font-size: 13px;
}
QWidget#attachmentThumbnails {
    background: #f8fafd;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
}
QPushButton#attachmentThumbnail {
    min-width: 92px;
    max-width: 120px;
    min-height: 68px;
    text-align: left;
    padding: 6px 8px;
    font-size: 12px;
    line-height: 1.2;
}
QPushButton#attachmentThumbnail:hover {
    border-color: #1f6feb;
    background: #f0f7ff;
}
QLabel#attachmentThumbnailOverflow {
    color: #667085;
    padding: 8px;
    font-size: 12px;
}
QListWidget::item {
    padding: 10px 12px;
}
QListWidget::item:selected {
    background: #e8f0ff;
    color: #0f172a;
}
QListWidget#folderList,
QListWidget#companyList,
QListWidget#messageList {
    font-size: 14px;
}
QWidget#folderButtonsWidget {
    background: transparent;
}
QPushButton#folderButton {
    text-align: left;
    background: #f7f9fc;
    border: 1px solid #d7deea;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 30px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#folderButton:hover {
    background: #eef4ff;
    border-color: #9db2d0;
}
QPushButton#folderButton:checked {
    background: #e4efff;
    border-color: #7ea6e8;
    color: #0f3d86;
}
QListWidget#messageList::item {
    min-height: 44px;
    padding: 8px 12px;
    border-bottom: 1px solid #eef2f7;
}
QListWidget#messageList::item:alternate {
    background: #fbfcfe;
}
QListWidget#companyList::item {
    padding: 10px;
    margin: 3px 0;
    border: 1px solid #e6ebf2;
    border-radius: 6px;
}
QListWidget#companyList::item:selected {
    background: #dfeeff;
    border: 1px solid #93b7ef;
    color: #0f172a;
    font-weight: 600;
}
"""
