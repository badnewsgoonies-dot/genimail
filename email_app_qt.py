import faulthandler
import sys

faulthandler.enable()  # Dump traceback on segfault/crash to stderr

try:
    from PySide6.QtWidgets import QApplication
except ImportError as exc:
    print("PySide6 is required. Install with: pip install PySide6")
    raise

from genimail.constants import APP_NAME
from genimail.infra.config_store import Config
from genimail_qt.theme import style_for_theme
from genimail_qt.window import GeniMailQtWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    config = Config()
    app.setStyleSheet(style_for_theme(config.get("theme_mode")))
    window = GeniMailQtWindow(config=config)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
