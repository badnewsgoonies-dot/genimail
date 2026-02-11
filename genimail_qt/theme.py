LIGHT_APP_STYLE = """
QWidget {
    font-size: 13px;
}
QMainWindow {
    background-color: #FAF8F5;
}
QFrame#topBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E8E4DE;
}
QLabel#appTitle {
    color: #3D405B;
    font-size: 20px;
    font-weight: 700;
}
QLabel#statusLabel {
    color: #6B6E8A;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #E8E4DE;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: #F0EDE8;
    border: 1px solid #E8E4DE;
    border-bottom-color: #E8E4DE;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    min-width: 136px;
    min-height: 36px;
    padding: 8px 14px;
    color: #6B6E8A;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #3D405B;
    border-bottom-color: #ffffff;
    font-weight: 600;
}
QPushButton {
    background: #F0EDE8;
    border: 1px solid #E8E4DE;
    border-radius: 8px;
    color: #3D405B;
    padding: 8px 12px;
    min-height: 32px;
}
QPushButton:hover {
    border-color: #C96A52;
    background: #F5F2ED;
}
QPushButton:disabled {
    color: #98a2b3;
    background: #f7f8fa;
    border-color: #e5e7eb;
}
QPushButton#primaryButton {
    background: #E07A5F;
    border-color: #E07A5F;
    color: white;
}
QPushButton#primaryButton:hover {
    background: #C96A52;
    border-color: #C96A52;
}
QPushButton#themeToggleButton {
    min-height: 30px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#themeToggleButton:checked {
    background: #3D405B;
    border-color: #3D405B;
    color: #ffffff;
}
QPushButton#companySectionButton {
    text-align: left;
    font-weight: 600;
    background: #F0EDE8;
    border-color: #E8E4DE;
}
QPushButton#companySectionButton:hover {
    background: #F5F2ED;
}
QPushButton#companyInlineButton {
    padding: 4px 8px;
    min-height: 24px;
    background: #FAF8F5;
}
QPushButton#companyInlineButton:hover {
    background: #F5F2ED;
    border-color: #C96A52;
}
QPushButton#emailDensityButton {
    padding: 4px 10px;
    min-height: 24px;
    font-size: 12px;
    background: #FAF8F5;
    border: 1px solid #E8E4DE;
    color: #6B6E8A;
}
QPushButton#emailDensityButton:hover {
    background: #F5F2ED;
    border-color: #D5D2CC;
}
QPushButton#emailDensityButton:checked {
    background: #F4D1C7;
    border-color: #E07A5F;
    color: #3D405B;
    font-weight: 600;
}
QScrollArea#companyTabsScroll {
    background: transparent;
}
QWidget#companyTabsContainer {
    background: transparent;
}
QPushButton#companyTabButton {
    background: #FAF8F5;
    border: 1px solid #E8E4DE;
    border-radius: 999px;
    color: #6B6E8A;
    padding: 6px 12px;
    min-height: 28px;
}
QPushButton#companyTabButton:hover {
    background: #F5F2ED;
    border-color: #D5D2CC;
}
QPushButton#companyTabButton:checked {
    background: #F4D1C7;
    border-color: #E07A5F;
    color: #3D405B;
    font-weight: 600;
}
QWidget#companyFolderFilterWidget {
    background: transparent;
}
QPushButton#companyFolderChip {
    background: #FAF8F5;
    border: 1px solid #E8E4DE;
    border-radius: 999px;
    color: #6B6E8A;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton#companyFolderChip:hover {
    background: #F5F2ED;
    border-color: #D5D2CC;
}
QPushButton#companyFolderChip:checked {
    background: #F4D1C7;
    border-color: #E07A5F;
    color: #3D405B;
    font-weight: 600;
}
QPushButton#backToListBtn {
    background: transparent;
    border: none;
    color: #E07A5F;
    font-weight: 600;
    padding: 4px 8px;
}
QPushButton#backToListBtn:hover {
    text-decoration: underline;
    background: transparent;
    border: none;
}
QLabel#companyFilterBadge {
    background: #FDF0EC;
    border: 1px solid #F4D1C7;
    border-radius: 8px;
    color: #8A3A2A;
    padding: 6px 10px;
    font-size: 13px;
}
QLabel#messageHeader {
    color: #3D405B;
    font-size: 14px;
    font-weight: 600;
    padding: 2px 0 4px 0;
}
QFrame#toastFrame {
    background: #3D405B;
    border-radius: 8px;
    border: 1px solid #4A4D6A;
}
QFrame#toastFrame[toastKind="success"] {
    background: #81B29A;
    border-color: #81B29A;
}
QFrame#toastFrame[toastKind="error"] {
    background: #E07A5F;
    border-color: #E07A5F;
}
QLabel#toastLabel {
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
}
QLineEdit, QTextEdit, QListWidget {
    border: 1px solid #E8E4DE;
    border-radius: 8px;
    background: #ffffff;
    color: #3D405B;
    font-size: 13px;
}
QLineEdit, QTextEdit {
    padding: 8px 10px;
    min-height: 34px;
}
QGroupBox {
    border: 1px solid #E8E4DE;
    border-radius: 8px;
    margin-top: 12px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #6B6E8A;
    font-weight: 600;
    font-size: 13px;
}
QWidget#attachmentThumbnails {
    background: #FAF8F5;
    border: 1px solid #E8E4DE;
    border-radius: 8px;
}
QPushButton#attachmentThumbnail {
    min-width: 110px;
    max-width: 150px;
    min-height: 72px;
    text-align: center;
    padding: 8px 10px;
    font-size: 11px;
    color: #6B6E8A;
    background: #FFFFFF;
    border: 1px solid #E8E4DE;
    border-radius: 6px;
}
QPushButton#attachmentThumbnail:hover {
    border-color: #E07A5F;
    background: #FDF0EC;
    color: #3D405B;
}
QLabel#attachmentThumbnailOverflow {
    color: #A0A3B5;
    padding: 8px;
    font-size: 12px;
}
QPushButton#downloadResultButton {
    background: #E8F5EE;
    border: 1px solid #81B29A;
    border-radius: 8px;
    padding: 6px 12px;
    color: #2D6E4F;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#downloadResultButton:hover {
    background: #D4EDE2;
    border-color: #6A9C83;
}
QListWidget::item {
    padding: 10px 12px;
}
QListWidget::item:selected {
    background: #F4D1C7;
    color: #3D405B;
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
    background: #FAF8F5;
    border: 1px solid #E8E4DE;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 30px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#folderButton:hover {
    background: #F5F2ED;
    border-color: #D5D2CC;
}
QPushButton#folderButton:checked {
    background: #F4D1C7;
    border-color: #E07A5F;
    color: #3D405B;
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
    border: 1px solid #E8E4DE;
    border-radius: 8px;
}
QListWidget#companyList::item:selected {
    background: #F4D1C7;
    border: 1px solid #E07A5F;
    color: #3D405B;
    font-weight: 600;
}
QWidget#pdfToolPanel {
    background: #FAF8F5;
    border-right: 1px solid #E8E4DE;
}
QWidget#pdfToolPanel QLabel {
    font-size: 12px;
    color: #6B6E8A;
}
QWidget#pdfToolPanel QRadioButton {
    font-size: 12px;
    color: #3D405B;
    spacing: 4px;
}
QLabel#pdfCalStatus {
    font-size: 11px;
    color: #6B6E8A;
    padding: 2px 0;
}
QLabel#pdfResultLabel {
    font-size: 12px;
    color: #3D405B;
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
    background-color: #1A1814;
}
QFrame#topBar {
    background-color: #242019;
    border-bottom: 1px solid #3A352E;
}
QLabel#appTitle {
    color: #E8E4DE;
}
QLabel#statusLabel {
    color: #8b949e;
}
QTabWidget::pane {
    border: 1px solid #3A352E;
    background: #1E1B16;
}
QTabBar::tab {
    background: #242019;
    border: 1px solid #3A352E;
    border-bottom-color: #3A352E;
    color: #A0A3B5;
}
QTabBar::tab:selected {
    background: #1E1B16;
    color: #E8E4DE;
    border-bottom-color: #1E1B16;
}
QPushButton {
    background: #2A2620;
    border: 1px solid #4A443C;
    color: #E8E4DE;
}
QPushButton:hover {
    border-color: #5b6572;
    background: #3A352E;
}
QPushButton:disabled {
    color: #6e7681;
    background: #1E1B16;
    border-color: #3A352E;
}
QPushButton#primaryButton {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QPushButton#primaryButton:hover {
    background: #C96A52;
    border-color: #C96A52;
}
QPushButton#themeToggleButton {
    background: #1E1B16;
    border: 1px solid #4A443C;
    color: #E8E4DE;
}
QPushButton#themeToggleButton:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#themeToggleButton:checked {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QPushButton#companySectionButton {
    background: #242019;
    border-color: #4A443C;
    color: #c9d1d9;
}
QPushButton#companySectionButton:hover {
    background: #2A2620;
}
QPushButton#companyInlineButton {
    background: #1E1B16;
    border-color: #4A443C;
    color: #c9d1d9;
}
QPushButton#companyInlineButton:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#emailDensityButton {
    background: #1E1B16;
    border: 1px solid #4A443C;
    color: #A0A3B5;
}
QPushButton#emailDensityButton:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#emailDensityButton:checked {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QPushButton#companyTabButton {
    background: #242019;
    border: 1px solid #4A443C;
    color: #c9d1d9;
}
QPushButton#companyTabButton:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#companyTabButton:checked {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QPushButton#companyFolderChip {
    background: #1E1B16;
    border: 1px solid #4A443C;
    color: #A0A3B5;
}
QPushButton#companyFolderChip:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#companyFolderChip:checked {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QPushButton#backToListBtn {
    color: #E07A5F;
}
QLabel#companyFilterBadge {
    background: #3A2A20;
    border: 1px solid #6B4A3A;
    color: #F4D1C7;
}
QLabel#messageHeader {
    color: #E8E4DE;
}
QFrame#toastFrame {
    background: #1E1B16;
    border-color: #3A352E;
}
QLabel#toastLabel {
    color: #f8fafc;
}
QLineEdit, QTextEdit, QListWidget {
    border: 1px solid #4A443C;
    background: #1E1B16;
    color: #E8E4DE;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #E07A5F;
}
QGroupBox {
    border: 1px solid #3A352E;
    background: #1E1B16;
}
QGroupBox::title {
    color: #A0A3B5;
}
QWidget#attachmentThumbnails {
    background: #1E1B16;
    border: 1px solid #3A352E;
}
QPushButton#attachmentThumbnail {
    background: #2A2620;
    border: 1px solid #4A443C;
    color: #A0A3B5;
}
QPushButton#attachmentThumbnail:hover {
    border-color: #E07A5F;
    background: #3A302A;
    color: #E8E4DE;
}
QLabel#attachmentThumbnailOverflow {
    color: #A0A3B5;
}
QPushButton#downloadResultButton {
    background: #1E2E26;
    border: 1px solid #6A9C83;
    color: #81B29A;
}
QPushButton#downloadResultButton:hover {
    background: #263D32;
    border-color: #81B29A;
}
QListWidget::item:selected {
    background: #3A302A;
    color: #f8fafc;
}
QPushButton#folderButton {
    background: #242019;
    border: 1px solid #4A443C;
    color: #c9d1d9;
}
QPushButton#folderButton:hover {
    background: #2A2620;
    border-color: #5b6572;
}
QPushButton#folderButton:checked {
    background: #E07A5F;
    border-color: #E07A5F;
    color: #ffffff;
}
QListWidget#companyList::item {
    border: 1px solid #3A352E;
}
QListWidget#companyList::item:selected {
    background: #3A302A;
    border: 1px solid #E07A5F;
    color: #f8fafc;
}
QWidget#pdfToolPanel {
    background: #1E1B16;
    border-right: 1px solid #3A352E;
}
QWidget#pdfToolPanel QLabel {
    color: #A0A3B5;
}
QWidget#pdfToolPanel QRadioButton {
    color: #c9d1d9;
}
QLabel#pdfCalStatus {
    color: #8b949e;
}
QLabel#pdfResultLabel {
    color: #E8E4DE;
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
