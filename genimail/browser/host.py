import importlib

from tkinter import BOTH

from genimail.browser.errors import (
    BrowserFeatureUnavailableError,
    BrowserNavigationError,
)
from genimail.browser.navigation import validate_url
from genimail.browser.runtime import BrowserRuntimeStatus, detect_browser_runtime


class BrowserController:
    """WebView2-backed browser host for a single embedded surface."""

    def __init__(self, root, bg_color="#ffffff"):
        self.root = root
        self.bg_color = bg_color
        self._main_parent = None
        self._main_view = None
        self.runtime_info = detect_browser_runtime()

    def start(self, parent_frame) -> None:
        self._ensure_runtime_ready()
        if self._main_view is not None and self._main_parent is parent_frame:
            return
        if self._main_view is not None:
            self.dispose()

        self._main_parent = parent_frame
        self._main_view = self._create_webview(parent_frame)
        self._main_view.pack(fill=BOTH, expand=True)

    def is_initialized(self) -> bool:
        return self._main_view is not None

    def show_main(self):
        if self._main_view is not None:
            self._main_view.pack(fill=BOTH, expand=True)

    def hide_main(self):
        if self._main_view is not None:
            self._main_view.pack_forget()

    def load_html(self, html: str, base_url: str | None = None) -> None:
        view = self._resolve_view()
        try:
            view.load_html(html, base_url)
        except Exception as exc:
            raise BrowserNavigationError(f"Could not render HTML: {exc}") from exc

    def load_url(self, url: str) -> None:
        view = self._resolve_view()
        safe_url = validate_url(url)
        try:
            view.load_url(safe_url)
        except Exception as exc:
            raise BrowserNavigationError(f"Could not open URL: {exc}") from exc

    def get_current_url(self) -> str | None:
        view = self._resolve_view()
        try:
            return view.get_url()
        except Exception:
            return None

    def go_back(self) -> bool:
        view = self._resolve_view()
        core = getattr(view, "core", None)
        if core is None:
            return False
        try:
            if core.CanGoBack:
                core.GoBack()
                return True
        except Exception:
            return False
        return False

    def go_forward(self) -> bool:
        view = self._resolve_view()
        core = getattr(view, "core", None)
        if core is None:
            return False
        try:
            if core.CanGoForward:
                core.GoForward()
                return True
        except Exception:
            return False
        return False

    def reload(self) -> bool:
        view = self._resolve_view()
        core = getattr(view, "core", None)
        if core is None:
            return False
        try:
            core.Reload()
            return True
        except Exception:
            return False

    def dispose(self) -> None:
        if self._main_view is not None:
            try:
                self._main_view.destroy()
            except Exception:
                pass
        self._main_view = None
        self._main_parent = None

    def _resolve_view(self):
        self._ensure_runtime_ready()
        if self._main_view is None:
            raise BrowserNavigationError("Browser main view is not initialized.")
        return self._main_view

    def _create_webview(self, parent):
        _apply_edgechrome_compat_patch()
        from tkwebview2.tkwebview2 import WebView2

        width = max(int(parent.winfo_width() or parent.winfo_reqwidth() or 900), 320)
        height = max(int(parent.winfo_height() or parent.winfo_reqheight() or 560), 240)
        return WebView2(parent, width=width, height=height, bg=self.bg_color)

    def _ensure_runtime_ready(self):
        if self.runtime_info.status == BrowserRuntimeStatus.READY:
            return
        raise BrowserFeatureUnavailableError(self.runtime_info.detail)


def _apply_edgechrome_compat_patch():
    """Bridge tkwebview2 expectations across pywebview EdgeChrome versions."""
    try:
        module = importlib.import_module("webview.platforms.edgechromium")
    except Exception:
        return

    edge_chrome = getattr(module, "EdgeChrome", None)
    if edge_chrome is None:
        return

    if not hasattr(edge_chrome, "web_view"):
        edge_chrome.web_view = property(lambda self: getattr(self, "webview", None))
