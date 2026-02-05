import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError as exc:
    print("PySide6 is required. Install with: pip install PySide6")
    raise

from genimail.constants import APP_NAME
from genimail_qt.theme import APP_STYLE
from genimail_qt.window import GeniMailQtWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(APP_STYLE)
    window = GeniMailQtWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
