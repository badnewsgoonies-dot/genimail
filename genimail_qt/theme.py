LIGHT_APP_STYLE = """
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
QPushButton#themeToggleButton {
    min-height: 30px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#themeToggleButton:checked {
    background: #0f172a;
    border-color: #0f172a;
    color: #ffffff;
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
QPushButton#emailDensityButton {
    padding: 4px 10px;
    min-height: 24px;
    font-size: 12px;
    background: #f8fafc;
    border: 1px solid #d7deea;
    color: #475467;
}
QPushButton#emailDensityButton:hover {
    background: #f1f5ff;
    border-color: #9db2d0;
}
QPushButton#emailDensityButton:checked {
    background: #e8f0ff;
    border-color: #7ea6e8;
    color: #0f3d86;
    font-weight: 600;
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
QPushButton#downloadResultButton {
    background: #ecfdf5;
    border: 1px solid #6ee7b7;
    border-radius: 6px;
    padding: 6px 12px;
    color: #065f46;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#downloadResultButton:hover {
    background: #d1fae5;
    border-color: #34d399;
}
QListWidget::item {
    padding: 10px 12px;
}
QListWidget::item:selected {
    background: #e8f0ff;
    color: #0f172a;
}
QListWidget#folderList,
QListWidget#companyList {
    font-size: 14px;
}
QListWidget#messageList {
    font-size: 13px;
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
    min-height: 0;
    padding: 0;
}
QListWidget#messageList::item:selected {
    background: transparent;
}
QListWidget#messageList::item:alternate {
    background: transparent;
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
QWidget#pdfToolPanel {
    background: #f7f9fc;
    border-right: 1px solid #dfe3ea;
}
QWidget#pdfToolPanel QLabel {
    font-size: 12px;
    color: #475467;
}
QWidget#pdfToolPanel QRadioButton {
    font-size: 12px;
    color: #1f2937;
    spacing: 4px;
}
QLabel#pdfCalStatus {
    font-size: 11px;
    color: #334155;
    padding: 2px 0;
}
QLabel#pdfResultLabel {
    font-size: 12px;
    color: #1f2937;
    font-weight: 600;
    padding: 1px 0;
}
QWidget#pdfToolPanel QPushButton {
    padding: 4px 8px;
    min-height: 26px;
    font-size: 12px;
}
QWidget#pdfToolPanel QLineEdit {
    min-height: 28px;
    padding: 4px 8px;
    font-size: 12px;
}
"""

DARK_APP_STYLE_OVERRIDES = """
QMainWindow {
    background-color: #0d1117;
}
QFrame#topBar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
}
QLabel#appTitle {
    color: #e6edf3;
}
QLabel#statusLabel {
    color: #8b949e;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    background: #0f1720;
}
QTabBar::tab {
    background: #161b22;
    border: 1px solid #30363d;
    border-bottom-color: #30363d;
    color: #9aa4b2;
}
QTabBar::tab:selected {
    background: #0f1720;
    color: #f0f6fc;
    border-bottom-color: #0f1720;
}
QPushButton {
    background: #21262d;
    border: 1px solid #3a4149;
    color: #e6edf3;
}
QPushButton:hover {
    border-color: #5b6572;
    background: #30363d;
}
QPushButton:disabled {
    color: #6e7681;
    background: #171b20;
    border-color: #2b3138;
}
QPushButton#primaryButton {
    background: #2f81f7;
    border-color: #2f81f7;
    color: #ffffff;
}
QPushButton#primaryButton:hover {
    background: #1f6feb;
    border-color: #1f6feb;
}
QPushButton#themeToggleButton {
    background: #0f1720;
    border: 1px solid #3a4149;
    color: #e6edf3;
}
QPushButton#themeToggleButton:hover {
    background: #1a2331;
    border-color: #5b6572;
}
QPushButton#themeToggleButton:checked {
    background: #2f81f7;
    border-color: #2f81f7;
    color: #ffffff;
}
QPushButton#companySectionButton {
    background: #161b22;
    border-color: #3a4149;
    color: #c9d1d9;
}
QPushButton#companySectionButton:hover {
    background: #1d2430;
}
QPushButton#companyInlineButton {
    background: #171d24;
    border-color: #3a4149;
    color: #c9d1d9;
}
QPushButton#companyInlineButton:hover {
    background: #1e2733;
    border-color: #5b6572;
}
QPushButton#emailDensityButton {
    background: #151c26;
    border: 1px solid #3a4149;
    color: #9aa4b2;
}
QPushButton#emailDensityButton:hover {
    background: #1e2733;
    border-color: #5b6572;
}
QPushButton#emailDensityButton:checked {
    background: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#companyTabButton {
    background: #161b22;
    border: 1px solid #3a4149;
    color: #c9d1d9;
}
QPushButton#companyTabButton:hover {
    background: #1f2733;
    border-color: #5b6572;
}
QPushButton#companyTabButton:checked {
    background: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#companyFolderChip {
    background: #151c26;
    border: 1px solid #3a4149;
    color: #9aa4b2;
}
QPushButton#companyFolderChip:hover {
    background: #1e2733;
    border-color: #5b6572;
}
QPushButton#companyFolderChip:checked {
    background: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#backToListBtn {
    color: #6cb6ff;
}
QLabel#companyFilterBadge {
    background: #10243d;
    border: 1px solid #244b74;
    color: #9ecbff;
}
QLabel#messageHeader {
    color: #f0f6fc;
}
QFrame#toastFrame {
    background: #111827;
    border-color: #334155;
}
QLabel#toastLabel {
    color: #f8fafc;
}
QLineEdit, QTextEdit, QListWidget {
    border: 1px solid #3a4149;
    background: #111827;
    color: #e6edf3;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #2f81f7;
}
QGroupBox {
    border: 1px solid #30363d;
    background: #0f1720;
}
QGroupBox::title {
    color: #9aa4b2;
}
QWidget#attachmentThumbnails {
    background: #111827;
    border: 1px solid #30363d;
}
QPushButton#attachmentThumbnail:hover {
    border-color: #2f81f7;
    background: #1e2a38;
}
QLabel#attachmentThumbnailOverflow {
    color: #9aa4b2;
}
QPushButton#downloadResultButton {
    background: #0f2b24;
    border: 1px solid #2a7a68;
    color: #9ff7db;
}
QPushButton#downloadResultButton:hover {
    background: #12352d;
    border-color: #34a18a;
}
QListWidget::item:selected {
    background: #1e293b;
    color: #f8fafc;
}
QPushButton#folderButton {
    background: #161b22;
    border: 1px solid #3a4149;
    color: #c9d1d9;
}
QPushButton#folderButton:hover {
    background: #1f2733;
    border-color: #5b6572;
}
QPushButton#folderButton:checked {
    background: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QListWidget#companyList::item {
    border: 1px solid #30363d;
}
QListWidget#companyList::item:selected {
    background: #1e293b;
    border: 1px solid #2f81f7;
    color: #f8fafc;
}
QWidget#pdfToolPanel {
    background: #0f1720;
    border-right: 1px solid #30363d;
}
QWidget#pdfToolPanel QLabel {
    color: #9aa4b2;
}
QWidget#pdfToolPanel QRadioButton {
    color: #c9d1d9;
}
QLabel#pdfCalStatus {
    color: #8b949e;
}
QLabel#pdfResultLabel {
    color: #e6edf3;
}
"""

THEME_LIGHT = "light"
THEME_DARK = "dark"


def normalize_theme_mode(value):
    return THEME_DARK if str(value or "").strip().lower() == THEME_DARK else THEME_LIGHT


def style_for_theme(mode):
    normalized = normalize_theme_mode(mode)
    if normalized == THEME_DARK:
        return f"{LIGHT_APP_STYLE}\n{DARK_APP_STYLE_OVERRIDES}"
    return LIGHT_APP_STYLE


# Backwards compatibility for existing imports.
APP_STYLE = LIGHT_APP_STYLE

__all__ = [
    "APP_STYLE",
    "DARK_APP_STYLE_OVERRIDES",
    "LIGHT_APP_STYLE",
    "THEME_DARK",
    "THEME_LIGHT",
    "normalize_theme_mode",
    "style_for_theme",
]
