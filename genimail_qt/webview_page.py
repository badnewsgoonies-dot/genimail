import os

from PySide6.QtWebEngineCore import QWebEnginePage

from genimail_qt.constants import JS_CONSOLE_DEBUG_ENV
from genimail_qt.webview_utils import is_js_noise_message, is_local_console_source


class FilteredWebEnginePage(QWebEnginePage):
    def __init__(self, surface_name, parent=None):
        super().__init__(parent)
        self._surface_name = surface_name

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if os.getenv(JS_CONSOLE_DEBUG_ENV, "").strip() == "1":
            super().javaScriptConsoleMessage(level, message, line_number, source_id)
            return
        if is_js_noise_message(message):
            return
        if is_local_console_source(source_id):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                print(f"[WEB][{self._surface_name}] {message} ({source_id}:{line_number})")
            return


__all__ = ["FilteredWebEnginePage"]
