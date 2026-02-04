from dataclasses import dataclass
from tkinter import BOTH, Frame, Toplevel
from uuid import uuid4

from genimail.browser.errors import (
    BrowserFeatureUnavailableError,
    BrowserNavigationError,
)
from genimail.browser.navigation import validate_url
from genimail.browser.runtime import BrowserRuntimeStatus, detect_browser_runtime


@dataclass(frozen=True)
class BrowserTabHandle:
    tab_id: str
    title: str


class BrowserController:
    """WebView2-backed browser host for embedded and popup tabs."""

    def __init__(self, root, bg_color="#ffffff"):
        self.root = root
        self.bg_color = bg_color
        self._main_parent = None
        self._main_view = None
        self._tabs = {}
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

    def show_main(self):
        if self._main_view is not None:
            self._main_view.pack(fill=BOTH, expand=True)

    def hide_main(self):
        if self._main_view is not None:
            self._main_view.pack_forget()

    def load_html(self, html: str, base_url: str | None = None, tab_id: str | None = None) -> None:
        view = self._resolve_view(tab_id)
        try:
            view.load_html(html, base_url)
        except Exception as exc:
            raise BrowserNavigationError(f"Could not render HTML: {exc}") from exc

    def load_url(self, url: str, tab_id: str | None = None) -> None:
        view = self._resolve_view(tab_id)
        safe_url = validate_url(url)
        try:
            view.load_url(safe_url)
        except Exception as exc:
            raise BrowserNavigationError(f"Could not open URL: {exc}") from exc

    def open_new_tab(self, label: str) -> BrowserTabHandle:
        self._ensure_runtime_ready()
        tab_id = f"tab-{uuid4().hex[:10]}"
        win = Toplevel(self.root)
        win.title(label or "Browser")
        win.geometry("1000x760")
        win.configure(bg=self.bg_color)

        host = Frame(win, bg=self.bg_color)
        host.pack(fill=BOTH, expand=True)
        view = self._create_webview(host)
        view.pack(fill=BOTH, expand=True)

        self._tabs[tab_id] = {"window": win, "view": view}
        win.protocol("WM_DELETE_WINDOW", lambda tab=tab_id: self.close_tab(tab))
        return BrowserTabHandle(tab_id=tab_id, title=label or "Browser")

    def close_tab(self, tab_id: str) -> None:
        item = self._tabs.pop(tab_id, None)
        if not item:
            return
        window = item.get("window")
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass

    def get_current_url(self, tab_id: str | None = None) -> str | None:
        view = self._resolve_view(tab_id)
        try:
            return view.get_url()
        except Exception:
            return None

    def dispose(self) -> None:
        for tab_id in list(self._tabs.keys()):
            self.close_tab(tab_id)
        self._tabs.clear()
        if self._main_view is not None:
            try:
                self._main_view.destroy()
            except Exception:
                pass
        self._main_view = None
        self._main_parent = None

    def _resolve_view(self, tab_id: str | None):
        self._ensure_runtime_ready()
        if tab_id:
            item = self._tabs.get(tab_id)
            if not item:
                raise BrowserNavigationError(f"Browser tab does not exist: {tab_id}")
            return item["view"]
        if self._main_view is None:
            raise BrowserNavigationError("Browser main view is not initialized.")
        return self._main_view

    def _create_webview(self, parent):
        from tkwebview2.tkwebview2 import WebView2

        width = max(int(parent.winfo_width() or parent.winfo_reqwidth() or 900), 320)
        height = max(int(parent.winfo_height() or parent.winfo_reqheight() or 560), 240)
        return WebView2(parent, width=width, height=height, bg=self.bg_color)

    def _ensure_runtime_ready(self):
        if self.runtime_info.status == BrowserRuntimeStatus.READY:
            return
        raise BrowserFeatureUnavailableError(self.runtime_info.detail)

