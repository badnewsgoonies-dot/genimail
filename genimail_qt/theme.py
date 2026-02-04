APP_STYLE = """
QMainWindow {
    background-color: #f5f6f8;
}
QFrame#topBar {
    background-color: #fdfdfd;
    border-bottom: 1px solid #dfe3ea;
}
QLabel#appTitle {
    color: #1b1f24;
    font-size: 17px;
    font-weight: 700;
}
QLabel#statusLabel {
    color: #586171;
    font-size: 12px;
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
    min-width: 120px;
    min-height: 30px;
    padding: 6px 12px;
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
    padding: 6px 10px;
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
QLineEdit, QTextEdit, QListWidget {
    border: 1px solid #d2d8e2;
    border-radius: 6px;
    background: #ffffff;
    color: #0f172a;
}
QLineEdit, QTextEdit {
    padding: 6px 8px;
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
}
QListWidget::item {
    padding: 6px 8px;
}
QListWidget::item:selected {
    background: #e8f0ff;
    color: #0f172a;
}
"""
