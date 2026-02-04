"""
Genis Email Hub v2 - Paper Studio Edition
Outlook/Hotmail Email Client with warm, paper-inspired aesthetic.
Uses MSAL + Microsoft Graph API for authentication and email operations.
"""

import os
import threading
import hashlib
import base64
from datetime import datetime
from tkinter import (
    Tk, Frame, Label, Entry, Text, Button, Scrollbar, Canvas,
    Toplevel, StringVar, messagebox, filedialog,
    Menu, VERTICAL, HORIZONTAL, BOTH, LEFT, RIGHT, BOTTOM,
    X, Y, W, E, NW, WORD, END, DISABLED, NORMAL, FLAT,
)
from tkinter import ttk

from pdf_viewer import PdfViewerFrame
try:
    from scanner_app_v4 import ScannerAppV4
except Exception:
    ScannerAppV4 = None

from genimail.constants import (
    APP_NAME,
    DEFAULT_CLIENT_ID,
    FOLDER_DISPLAY,
    POLL_INTERVAL_MS,
)
from genimail.browser import (
    BrowserController,
    BrowserDownloadError,
    BrowserFeatureUnavailableError,
    download_url_content,
    require_pdf_bytes,
)
from genimail.browser.navigation import wrap_plain_text_as_html
from genimail.domain.helpers import (
    domain_to_company,
    format_date,
    format_size,
    strip_html,
    token_cache_path_for_client_id,
)
from genimail.domain.link_tools import collect_cloud_pdf_links
from genimail.infra.cache_store import EmailCache
from genimail.infra.config_store import Config
from genimail.infra.graph_client import GraphClient
from genimail.paths import (
    CONFIG_FILE,
    PDF_DIR,
)
from genimail.services.mail_sync import MailSyncService, collect_new_unread
from genimail.ui.dialogs import AttachmentBrowser, CloudPdfLinkDialog, CompanyManagerDialog, ComposeWindow
from genimail.ui.splash import SplashScreen
from genimail.ui.tabs import build_preview_tabs
from genimail.ui.theme import T
from genimail.ui.widgets import StyledEntry, WarmButton

try:
    import msal
except ImportError:
    msal = None

try:
    import requests
except ImportError:
    requests = None

try:
    from winotify import Notification
    HAS_WINOTIFY = True
except ImportError:
    HAS_WINOTIFY = False


# Theme aliases used by current UI shell.

COLOR_ACCENT = T.ACCENT
COLOR_ACCENT_HOVER = T.ACCENT_HOVER
COLOR_BORDER = T.BORDER
COLOR_BG_LIGHT = T.BG_MUTED
COLOR_BG_MED = T.BG_MUTED
COLOR_BG_SIDEBAR = T.BG_MUTED
COLOR_BG_WHITE = T.BG_SURFACE
COLOR_UNREAD = T.UNREAD
COLOR_READ = T.READ
COLOR_TEXT = T.TEXT_PRIMARY
FONT_HEADER = T.FONT_HEADER
FONT_NORMAL = T.FONT_LABEL
FONT_SMALL = T.FONT_SMALL
FONT_SUBJECT = T.FONT_SUBJECT
FONT_BODY = T.FONT_BODY

COMPANY_COLORS = [
    "#E07A5F", "#81B29A", "#F2CC8F", "#3D405B", "#D4A373",
    "#A8DADC", "#E9C46A", "#2A9D8F", "#264653", "#F4A261",
]


class EmailApp:
    """Main email application."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.config = Config()
        self._config_load_error = self.config.load_error
        self.browser_engine = (self.config.get("browser_engine", "webview2") or "webview2").strip().lower()
        if self.browser_engine != "webview2":
            self.browser_engine = "webview2"
            self.config.set("browser_engine", "webview2")
        self.root.geometry(self.config.get("window_geometry", "1100x700"))
        self.root.minsize(900, 550)

        # Try to set theme matching scanner app
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            try:
                style.theme_use("clam")
            except Exception:
                pass

        self.graph = None
        self.messages = []
        self.current_folder = "inbox"
        self.current_message = None
        self.folders = []
        self.folder_counts = {}
        self.companies = {}       # domain -> {"name": str, "color": str, "count": int}
        self.all_messages = []     # flat cache for attachment browser
        self.search_query = ""
        self.user_email = ""
        self.user_name = ""
        self._poll_id = None
        self._poll_lock = threading.Lock()
        self._loading = False

        # Performance: caches
        self.message_cache = {}      # msg_id -> full message body + metadata
        self.attachment_cache = {}   # msg_id -> list of attachments
        self.cloud_link_cache = {}   # msg_id -> list of cloud/external PDF links
        self.known_ids = set()       # tracked message IDs for smarter polling
        self._poll_failures = 0      # consecutive poll failure count for backoff
        self._browser_runtime_notified = False
        self._browser_controller = None
        self._browser_tab_controller = None
        self._raw_html_content = None
        self._plain_fallback_content = ""

        # SQLite persistent cache
        self.cache = EmailCache()
        self.sync_service = None

        # Virtual scrolling state
        self._visible_start = 0
        self._visible_count = 15
        self._row_height = 72
        self._filtered_messages = []  # current filtered message list for virtual scroll
        self._canvas_items = {}       # index -> list of canvas item IDs

        # Company color assignment counter
        self._color_idx = 0

        # Check dependencies
        if not msal or not requests:
            missing = []
            if not msal:
                missing.append("msal")
            if not requests:
                missing.append("requests")
            messagebox.showerror("Missing Dependencies",
                                 f"Please install required packages:\n\n"
                                 f"  pip install {' '.join(missing)}\n\n"
                                 f"Then restart the application.")
            root.destroy()
            return

        self._build_ui()
        if self._config_load_error:
            messagebox.showwarning(
                "Config Warning",
                f"Could not fully read config file:\n{CONFIG_FILE}\n\n"
                f"Using defaults for this run.\n\nError: {self._config_load_error}",
                parent=self.root,
            )
        self._try_connect()

    def _try_connect(self):
        """Attempt connection using device code flow."""
        self._connect()

    def _connect(self):
        """Authenticate and load initial data using device code flow."""
        self.status_var.set("Connecting...")

        def on_device_code(flow):
            code = flow.get("user_code", "???")
            msg = f"Sign in: go to microsoft.com/devicelogin and enter code {code}"
            print(f"[AUTH] {msg}")
            self.root.after(0, lambda: self.status_var.set(msg))
            self.root.after(0, lambda: self._show_code_popup(code))

        client_id = (self.config.get("client_id") or "").strip() or None
        self.graph = GraphClient(client_id=client_id, on_device_code=on_device_code)
        self.sync_service = MailSyncService(self.graph, self.cache)

        def do_auth():
            try:
                print("[AUTH] Starting authentication...")
                success = self.graph.authenticate()
                print(f"[AUTH] Result: {success}")
                if success:
                    profile = self.graph.get_profile()
                    self.user_email = profile.get("mail", profile.get("userPrincipalName", ""))
                    self.user_name = profile.get("displayName", "")
                    print(f"[AUTH] Logged in as {self.user_email}")
                    self.root.after(0, self._on_connected)
                else:
                    print("[AUTH] Authentication returned False")
                    self.root.after(0, lambda: self._on_auth_fail("Authentication failed."))
            except Exception as e:
                err_msg = str(e)
                print(f"[AUTH] Error: {err_msg}")
                self.root.after(0, lambda msg=err_msg: self._on_auth_fail(msg))

        threading.Thread(target=do_auth, daemon=True).start()

    def _show_code_popup(self, code):
        """Show device code in a simple messagebox that can't hide."""
        messagebox.showinfo(
            "Sign In to Microsoft",
            f"A browser window has opened.\n\n"
            f"Enter this code when prompted:\n\n"
            f"    {code}\n\n"
            f"Sign in with your Microsoft account.\n"
            f"(This dialog will close automatically when done)",
            parent=self.root
        )

    def _on_connected(self):
        self.root.title(f"{APP_NAME} - {self.user_email}")
        self.status_var.set(f"Connected as {self.user_email}")
        # Prune old cache entries on startup (non-critical, don't crash on failure)
        try:
            self.cache.prune_old(days=30)
        except Exception as e:
            print(f"[CACHE] Prune failed: {e}")
        self._load_folders()
        # Try cache-first loading for instant display
        self._load_cached_messages()
        # Then sync with server in background
        self._load_messages()
        self._start_polling()

    def _on_auth_fail(self, msg):
        self.status_var.set("Not connected")
        result = messagebox.askretrycancel(
            "Authentication Failed",
            f"Could not sign in:\n{msg}\n\nWould you like to try again?")
        if result:
            self._connect()

    def _build_ui(self):
        """Build the 3-panel UI with Paper Studio styling."""
        # Configure root background
        self.root.configure(bg=T.BG_BASE)
        
        # Status bar at bottom
        status_frame = Frame(self.root, bg=T.BG_MUTED, height=28)
        status_frame.pack(side=BOTTOM, fill=X)
        status_frame.pack_propagate(False)

        self.status_var = StringVar(value="Starting...")
        Label(status_frame, textvariable=self.status_var, font=T.FONT_SMALL,
              bg=T.BG_MUTED, fg=T.TEXT_SECONDARY, padx=12).pack(side=LEFT)

        self.msg_count_var = StringVar(value="")
        Label(status_frame, textvariable=self.msg_count_var, font=T.FONT_SMALL,
              bg=T.BG_MUTED, fg=T.TEXT_MUTED).pack(side=RIGHT, padx=12)

        self.sync_var = StringVar(value="")
        Label(status_frame, textvariable=self.sync_var, font=T.FONT_SMALL,
              bg=T.BG_MUTED, fg=T.TEXT_MUTED).pack(side=RIGHT, padx=8)

        # Main paned window
        self.paned = ttk.PanedWindow(self.root, orient=HORIZONTAL)
        self.paned.pack(fill=BOTH, expand=True)

        # -- Sidebar --
        self.sidebar = Frame(self.paned, bg=T.BG_MUTED, width=T.SIDEBAR_W)
        self.paned.add(self.sidebar, weight=0)

        # App title in sidebar
        title_frame = Frame(self.sidebar, bg=T.BG_MUTED, padx=12, pady=12)
        title_frame.pack(fill=X)
        Label(title_frame, text="Email Hub", font=T.FONT_DISPLAY,
              bg=T.BG_MUTED, fg=T.TEXT_PRIMARY).pack(anchor=W)

        # Search in sidebar
        search_frame = Frame(self.sidebar, bg=T.BG_MUTED, padx=12, pady=8)
        search_frame.pack(fill=X)
        self.search_var = StringVar()
        self.search_styled = StyledEntry(search_frame, textvariable=self.search_var, 
                                         placeholder="Search emails...", bg=T.BG_MUTED)
        self.search_styled.pack(fill=X)
        self.search_styled.bind("<Return>", lambda e: self._do_search())
        self.search_entry = self.search_styled.entry

        # Folders section with sage tint
        folder_section = Frame(self.sidebar, bg=T.SECTION_FOLDERS, padx=12, pady=8)
        folder_section.pack(fill=X, pady=(8, 0))
        folder_header = Frame(folder_section, bg=T.SECTION_FOLDERS)
        folder_header.pack(fill=X)
        Label(folder_header, text="FOLDERS", font=T.FONT_SMALL,
              bg=T.SECTION_FOLDERS, fg=T.SECONDARY_HOVER).pack(anchor=W)

        self.folder_frame = Frame(folder_section, bg=T.SECTION_FOLDERS)
        self.folder_frame.pack(fill=X, pady=(4, 0))

        # Companies section with lavender tint
        comp_section = Frame(self.sidebar, bg=T.SECTION_COMPANIES, padx=12, pady=8)
        comp_section.pack(fill=X, pady=(8, 0))
        comp_header = Frame(comp_section, bg=T.SECTION_COMPANIES)
        comp_header.pack(fill=X)
        Label(comp_header, text="COMPANIES", font=T.FONT_SMALL,
              bg=T.SECTION_COMPANIES, fg=T.TERTIARY).pack(side=LEFT, anchor=W)
        manage_btn = Label(comp_header, text="Manage", font=T.FONT_SMALL,
                          bg=T.SECTION_COMPANIES, fg=T.TEXT_SECONDARY, cursor="hand2")
        manage_btn.pack(side=RIGHT)
        manage_btn.bind("<Button-1>", lambda e: self._open_company_manager())
        manage_btn.bind("<Enter>", lambda e: manage_btn.config(fg=T.TERTIARY))
        manage_btn.bind("<Leave>", lambda e: manage_btn.config(fg=T.TEXT_SECONDARY))

        self.company_frame = Frame(comp_section, bg=T.SECTION_COMPANIES)
        self.company_frame.pack(fill=X, pady=(4, 0))

        # Company canvas with scrollbar for many companies
        self.company_canvas = Canvas(self.company_frame, bg=T.SECTION_COMPANIES,
                                     highlightthickness=0, height=180)
        self.company_inner = Frame(self.company_canvas, bg=T.SECTION_COMPANIES)
        self.company_canvas.pack(fill=BOTH, expand=True)
        self.company_canvas_window = self.company_canvas.create_window(
            (0, 0), window=self.company_inner, anchor=NW)
        self.company_inner.bind("<Configure>",
                                lambda e: self.company_canvas.configure(
                                    scrollregion=self.company_canvas.bbox("all")))
        self.company_canvas.bind("<Configure>",
                                 lambda e: self.company_canvas.itemconfig(
                                     self.company_canvas_window, width=e.width))

        # Attachments button with warm cream tint
        att_frame = Frame(self.sidebar, bg=T.SECTION_INBOX, padx=12, pady=12)
        att_frame.pack(fill=X, side=BOTTOM)
        Label(att_frame, text="ATTACHMENTS", font=T.FONT_SMALL,
              bg=T.SECTION_INBOX, fg=T.HIGHLIGHT).pack(anchor=W, pady=(0, 6))
        WarmButton(att_frame, "Browse All", self._open_attachment_browser,
                  primary=True, width=180, height=34, bg=T.SECTION_INBOX).pack(anchor=W)

        # Settings / reconnect at very bottom
        settings_frame = Frame(self.sidebar, bg=T.BG_MUTED, padx=12, pady=8)
        settings_frame.pack(fill=X, side=BOTTOM)
        WarmButton(settings_frame, "Reconnect", self._reconnect,
                  primary=False, width=180, height=32, bg=T.BG_MUTED).pack(anchor=W)

        # -- Email List (center) --
        self.list_panel = Frame(self.paned, bg=T.BG_BASE)
        self.paned.add(self.list_panel, weight=1)

        # List header/filter bar
        list_header = Frame(self.list_panel, bg=T.BG_BASE, padx=12, pady=8)
        list_header.pack(fill=X)
        self.list_search_var = StringVar()
        self.list_search_styled = StyledEntry(list_header, textvariable=self.list_search_var,
                                              placeholder="Filter list...", bg=T.BG_BASE)
        self.list_search_styled.pack(fill=X)
        self.list_search_styled.bind("<KeyRelease>", lambda e: self._apply_filter())
        self.list_search_entry = self.list_search_styled.entry

        # Email list with virtual scrolling canvas
        list_container = Frame(self.list_panel, bg=T.BG_BASE)
        list_container.pack(fill=BOTH, expand=True)

        self.list_canvas = Canvas(list_container, bg=T.BG_BASE, highlightthickness=0)
        self.list_scrollbar = Scrollbar(list_container, orient=VERTICAL,
                                        command=self._on_virtual_scroll)

        self.list_scrollbar.pack(side=RIGHT, fill=Y)
        self.list_canvas.pack(fill=BOTH, expand=True)

        # Mouse wheel scrolling
        self.list_canvas.bind("<Enter>",
                              lambda e: self.list_canvas.bind_all("<MouseWheel>", self._on_list_scroll))
        self.list_canvas.bind("<Leave>",
                              lambda e: self.list_canvas.unbind_all("<MouseWheel>"))
        self.list_canvas.bind("<Configure>", self._on_canvas_resize)
        self.list_canvas.bind("<Button-1>", self._on_canvas_click)

        # Load more button (hidden initially)
        self.load_more_frame = Frame(self.list_panel, bg=T.BG_BASE)
        self.btn_load_more = Button(self.load_more_frame, text="Load More",
                                    font=T.FONT_LABEL, bg=T.BG_MUTED, fg=T.TEXT_SECONDARY,
                                    relief=FLAT, command=self._load_more)

        # -- Preview Panel (right) --
        self.preview_panel = Frame(self.paned, bg=T.BG_SURFACE)
        self.paned.add(self.preview_panel, weight=1)

        # Preview header
        self.preview_header = Frame(self.preview_panel, bg=T.BG_SURFACE, padx=16, pady=12)
        self.preview_header.pack(fill=X)

        self.preview_from = Label(self.preview_header, text="", font=T.FONT_HEADER,
                                  bg=T.BG_SURFACE, fg=T.TEXT_PRIMARY, anchor=W)
        self.preview_from.pack(fill=X)
        self.preview_subject = Label(self.preview_header, text="Select an email to read",
                                     font=T.FONT_HEADING, bg=T.BG_SURFACE,
                                     fg=T.TEXT_PRIMARY, anchor=W, wraplength=400)
        self.preview_subject.pack(fill=X, pady=(6, 0))
        self.preview_date = Label(self.preview_header, text="", font=T.FONT_SMALL,
                                  bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY, anchor=W)
        self.preview_date.pack(fill=X, pady=(4, 0))
        self.preview_to = Label(self.preview_header, text="", font=T.FONT_SMALL,
                                bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY, anchor=W, wraplength=400)
        self.preview_to.pack(fill=X)

        Frame(self.preview_panel, bg=T.BORDER, height=1).pack(fill=X)

        build_preview_tabs(
            app=self,
            pdf_viewer_cls=PdfViewerFrame,
            scanner_cls=ScannerAppV4,
            pdf_initial_dir=PDF_DIR,
        )

    # -- Web View Methods --

    def _activate_email_rich_view(self):
        self.preview_fallback_frame.pack_forget()
        self.email_browser_host.pack(fill=BOTH, expand=True)
        if self._browser_controller is not None:
            self._browser_controller.show_main()

    def _show_plain_fallback(self, text, status_message=None):
        if self._browser_controller is not None:
            self._browser_controller.hide_main()
        self.email_browser_host.pack_forget()
        self.preview_fallback_frame.pack(fill=BOTH, expand=True)
        self.preview_body.config(state=NORMAL)
        self.preview_body.delete("1.0", END)
        self.preview_body.insert("1.0", text or "")
        self.preview_body.config(state=DISABLED)
        if status_message:
            self.status_var.set(status_message)

    def _ensure_browser_controller(self, notify=True):
        """Create rich email embedded WebView2 host on first use."""
        if self._browser_controller is not None and self._browser_controller.is_initialized():
            return True
        if self._browser_controller is not None and not self._browser_controller.is_initialized():
            self._browser_controller = None

        try:
            self._browser_controller = BrowserController(self.root, bg_color=T.BG_SURFACE)
            self._browser_controller.start(self.email_browser_host)
            return True
        except BrowserFeatureUnavailableError as exc:
            if notify and not self._browser_runtime_notified:
                messagebox.showerror(
                    "WebView2 Unavailable",
                    f"{exc}\n\nInstall dependencies:\n  pip install tkwebview2 pywebview",
                    parent=self.root,
                )
                self._browser_runtime_notified = True
            self.status_var.set("Web view unavailable")
            self._browser_controller = None
            return False
        except Exception as e:
            print(f"[WEBVIEW] Error creating email browser host: {e}")
            if notify:
                messagebox.showerror("WebView2 Error", str(e), parent=self.root)
            self._browser_controller = None
            return False

    def _ensure_browser_tab_controller(self, notify=True):
        """Create Browser tab embedded WebView2 host on first use."""
        if self._browser_tab_controller is not None and self._browser_tab_controller.is_initialized():
            return True
        if self._browser_tab_controller is not None and not self._browser_tab_controller.is_initialized():
            self._browser_tab_controller = None

        try:
            self._browser_tab_controller = BrowserController(self.root, bg_color=T.BG_SURFACE)
            self._browser_tab_controller.start(self.browser_host)
            return True
        except BrowserFeatureUnavailableError as exc:
            if notify and not self._browser_runtime_notified:
                messagebox.showerror(
                    "WebView2 Unavailable",
                    f"{exc}\n\nInstall dependencies:\n  pip install tkwebview2 pywebview",
                    parent=self.root,
                )
                self._browser_runtime_notified = True
            self.status_var.set("Browser tab unavailable")
            self._browser_tab_controller = None
            return False
        except Exception as e:
            print(f"[WEBVIEW] Error creating browser tab host: {e}")
            if notify:
                messagebox.showerror("WebView2 Error", str(e), parent=self.root)
            self._browser_tab_controller = None
            return False

    def _render_html_preview(self):
        """Render message content rich-first with plain fallback only on failure."""
        if not self.current_message:
            return

        content = self._raw_html_content or wrap_plain_text_as_html(
            self.current_message.get("bodyPreview", "")
        )
        plain_fallback = self._plain_fallback_content or self.current_message.get("bodyPreview", "")

        if not self._ensure_browser_controller(notify=False):
            self._show_plain_fallback(plain_fallback, "Rich preview unavailable; using plain fallback")
            return

        try:
            self._activate_email_rich_view()
            self._browser_controller.load_html(content)
        except Exception as e:
            print(f"[WEBVIEW] Rich preview render failed: {e}")
            self._show_plain_fallback(plain_fallback, "Rich preview failed; using plain fallback")

    def _open_in_browser(self):
        """Open current email content in the built-in Browser tab."""
        if not self.current_message:
            messagebox.showinfo("No Email", "Select an email first.", parent=self.root)
            return

        if not self._ensure_browser_tab_controller():
            return

        content = self._raw_html_content or wrap_plain_text_as_html(
            self.current_message.get("bodyPreview", "")
        )
        try:
            self._browser_tab_controller.load_html(content)
            self.preview_notebook.select(self.browser_tab)
            self.browser_url_var.set("https://")
            self.status_var.set("Opened in Browser tab")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open in Browser tab:\n{e}", parent=self.root)

    def _on_browser_go(self):
        raw = (self.browser_url_var.get() or "").strip()
        if not raw:
            return
        url = raw if "://" in raw else f"https://{raw}"
        if not self._ensure_browser_tab_controller():
            return
        try:
            self._browser_tab_controller.load_url(url)
            self.preview_notebook.select(self.browser_tab)
            self.browser_url_var.set(url)
            self.status_var.set(f"Opened {url}")
        except Exception as e:
            messagebox.showerror("Browser Error", str(e), parent=self.root)

    def _on_browser_back(self):
        if not self._ensure_browser_tab_controller():
            return
        moved = self._browser_tab_controller.go_back()
        if moved:
            self.status_var.set("Browser: back")
        else:
            self.status_var.set("Browser: no back history")

    def _on_browser_forward(self):
        if not self._ensure_browser_tab_controller():
            return
        moved = self._browser_tab_controller.go_forward()
        if moved:
            self.status_var.set("Browser: forward")
        else:
            self.status_var.set("Browser: no forward history")

    def _on_browser_reload(self):
        if not self._ensure_browser_tab_controller():
            return
        if self._browser_tab_controller.reload():
            self.status_var.set("Browser: reloaded")
        else:
            self.status_var.set("Browser: reload unavailable")

    def _on_list_scroll(self, event):
        """Handle mouse wheel scrolling with virtual scroll."""
        delta = int(-1 * (event.delta / 120))
        new_start = self._visible_start + delta
        total = len(self._filtered_messages)
        new_start = max(0, min(new_start, total - self._visible_count))
        if new_start != self._visible_start:
            self._visible_start = new_start
            self._draw_visible_rows()
            self._update_scrollbar()

    def _on_virtual_scroll(self, *args):
        """Handle scrollbar-driven virtual scrolling."""
        if args[0] == "moveto":
            fraction = float(args[1])
            total = len(self._filtered_messages)
            new_start = int(fraction * total)
            new_start = max(0, min(new_start, total - self._visible_count))
            if new_start != self._visible_start:
                self._visible_start = new_start
                self._draw_visible_rows()
                self._update_scrollbar()
        elif args[0] == "scroll":
            delta = int(args[1])
            if args[2] == "pages":
                delta *= self._visible_count
            new_start = self._visible_start + delta
            total = len(self._filtered_messages)
            new_start = max(0, min(new_start, total - self._visible_count))
            if new_start != self._visible_start:
                self._visible_start = new_start
                self._draw_visible_rows()
                self._update_scrollbar()

    def _update_scrollbar(self):
        """Update scrollbar position based on virtual scroll state."""
        total = len(self._filtered_messages)
        if total <= self._visible_count:
            self.list_scrollbar.set(0, 1)
        else:
            first = self._visible_start / total
            last = min(1.0, (self._visible_start + self._visible_count) / total)
            self.list_scrollbar.set(first, last)

    def _on_canvas_resize(self, event):
        """Recalculate visible count on resize and redraw."""
        new_count = max(5, event.height // self._row_height)
        # Redraw on any resize (width affects text truncation, height affects row count)
        self._visible_count = new_count
        self._draw_visible_rows()
        self._update_scrollbar()

    def _on_canvas_click(self, event):
        """Handle click on virtual-scrolled canvas row."""
        row_idx = event.y // self._row_height
        actual_idx = self._visible_start + row_idx
        if 0 <= actual_idx < len(self._filtered_messages):
            self._select_message(self._filtered_messages[actual_idx])

    def _search_focus_in(self, event):
        if self.search_var.get() == "Search emails...":
            self.search_entry.delete(0, END)

    def _search_focus_out(self, event):
        if not self.search_var.get().strip():
            self.search_entry.insert(0, "Search emails...")

    def _filter_focus_in(self, event):
        if self.list_search_var.get() == "Filter list...":
            self.list_search_entry.delete(0, END)

    def _filter_focus_out(self, event):
        if not self.list_search_var.get().strip():
            self.list_search_entry.insert(0, "Filter list...")

    def _do_search(self):
        query = self.search_var.get().strip()
        if query == "Search emails..." or not query:
            self.search_query = ""
        else:
            self.search_query = query
        self.messages = []
        self._load_messages()

    def _apply_filter(self):
        """Filter the displayed email list locally."""
        query = self.list_search_var.get().strip().lower()
        if query == "filter list...":
            query = ""
        self._render_email_list(query)

    # -- Data Loading --

    def _load_folders(self):
        def do_load():
            try:
                self.folders = self.graph.get_folders()
                self.root.after(0, self._render_folders)
            except Exception:
                pass

        threading.Thread(target=do_load, daemon=True).start()

    def _load_cached_messages(self):
        """Load messages from SQLite cache for instant display."""
        try:
            cached = self.cache.get_messages(self.current_folder, limit=100)
            if cached:
                self.messages = cached
                # Update known_ids from cache
                for m in cached:
                    self.known_ids.add(m["id"])
                self._detect_companies()
                self._render_email_list()
                self._render_companies()
                cached_count = len(cached)
                self.status_var.set(f"Loaded {cached_count} emails from cache, syncing...")
                return True
        except Exception as e:
            print(f"[CACHE] Error loading from cache: {e}")
        return False

    def _load_messages(self, append=False):
        if self._loading:
            return
        self._loading = True
        skip = len(self.messages) if append else 0

        def do_load():
            try:
                if self.search_query:
                    msgs, _ = self.graph.get_messages(
                        folder_id=self.current_folder,
                        top=50,
                        skip=skip,
                        search=self.search_query,
                    )
                elif self.sync_service and not append:
                    msgs = self.sync_service.fetch_recent_messages(folder_id=self.current_folder, top=50)
                else:
                    msgs, _ = self.graph.get_messages(
                        folder_id=self.current_folder,
                        top=50,
                        skip=skip,
                    )
                if append:
                    self.messages.extend(msgs)
                else:
                    self.messages = msgs

                # Save to SQLite cache (write-through)
                if msgs and not self.search_query:
                    try:
                        self.cache.save_messages(msgs, self.current_folder)
                    except Exception as cache_err:
                        print(f"[CACHE] Error saving to cache: {cache_err}")

                # Update all_messages cache
                existing_ids = {m["id"] for m in self.all_messages}
                for m in msgs:
                    if m["id"] not in existing_ids:
                        self.all_messages.append(m)

                self.root.after(0, self._on_messages_loaded)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))
            finally:
                self._loading = False

        threading.Thread(target=do_load, daemon=True).start()

    def _on_messages_loaded(self):
        # Update known_ids incrementally
        for m in self.messages:
            self.known_ids.add(m["id"])
        self._detect_companies()
        self._render_email_list()
        self._render_companies()
        self._update_status()

    def _load_more(self):
        self._load_messages(append=True)

    def _detect_companies(self):
        """Auto-detect companies from sender domains."""
        saved_companies = self.config.get("companies", {})
        saved_colors = self.config.get("company_colors", {})
        domain_counts = {}

        for msg in self.messages:
            sender = msg.get("from", {}).get("emailAddress", {})
            address = sender.get("address", "")
            if "@" in address:
                domain = address.split("@")[1].lower()
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        self.companies = {}
        for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
            name = saved_companies.get(domain, domain_to_company(domain))
            if domain in saved_colors:
                color = saved_colors[domain]
            else:
                color = COMPANY_COLORS[self._color_idx % len(COMPANY_COLORS)]
                self._color_idx += 1
                saved_colors[domain] = color
            self.companies[domain] = {"name": name, "color": color, "count": count}

        self.config.set("company_colors", saved_colors)

    def _get_company_for_msg(self, msg):
        """Get company info for a message."""
        sender = msg.get("from", {}).get("emailAddress", {})
        address = sender.get("address", "")
        if "@" in address:
            domain = address.split("@")[1].lower()
            return self.companies.get(domain)
        return None

    # -- Rendering --

    def _render_folders(self):
        for w in self.folder_frame.winfo_children():
            w.destroy()

        # Build folder count map
        self.folder_counts = {}
        for f in self.folders:
            fname = f.get("displayName", "").lower().replace(" ", "")
            self.folder_counts[f["id"]] = f.get("unreadItemCount", 0)

        # Standard folders first
        well_known = ["inbox", "sentitems", "drafts", "archive", "deleteditems", "junkemail"]
        for wk in well_known:
            folder = None
            for f in self.folders:
                if f.get("displayName", "").lower().replace(" ", "") == wk or \
                   wk in str(f.get("id", "")).lower():
                    folder = f
                    break
            if not folder:
                # Try well-known folder name matching
                for f in self.folders:
                    display = f.get("displayName", "").lower()
                    if (wk == "inbox" and display == "inbox") or \
                       (wk == "sentitems" and "sent" in display) or \
                       (wk == "drafts" and "draft" in display) or \
                       (wk == "archive" and "archive" in display) or \
                       (wk == "deleteditems" and "delete" in display) or \
                       (wk == "junkemail" and "junk" in display):
                        folder = f
                        break
            if folder:
                self._add_folder_button(folder, wk)

    def _add_folder_button(self, folder, well_known_name):
        display_name = FOLDER_DISPLAY.get(well_known_name, folder.get("displayName", ""))
        unread = folder.get("unreadItemCount", 0)
        folder_id = folder["id"]

        frame = Frame(self.folder_frame, bg=T.SECTION_FOLDERS, cursor="hand2")
        frame.pack(fill=X, pady=2)

        is_active = (self.current_folder == folder_id or
                     (self.current_folder == well_known_name and
                      folder.get("displayName", "").lower().replace(" ", "") == well_known_name))

        # Paper Studio: pill-style selection with sage tint
        section_bg = T.SECTION_FOLDERS
        if is_active:
            bg = T.SECONDARY  # Sage green when active
            fg = T.TEXT_INVERSE
        else:
            bg = section_bg
            fg = T.TEXT_PRIMARY
        frame.configure(bg=bg, highlightbackground=T.BORDER if not is_active else T.SECONDARY,
                       highlightthickness=0)

        lbl = Label(frame, text=display_name, font=T.FONT_LABEL, bg=bg, fg=fg,
                    anchor=W, padx=10, pady=5)
        lbl.pack(side=LEFT, fill=X, expand=True)

        if unread > 0:
            count_bg = T.TEXT_INVERSE if is_active else T.SECONDARY
            count_fg = T.SECONDARY if is_active else T.TEXT_INVERSE
            count_lbl = Label(frame, text=str(unread), font=T.FONT_SMALL,
                              bg=count_bg, fg=count_fg, padx=6, pady=1)
            count_lbl.pack(side=RIGHT, padx=(0, 6))
            count_lbl.bind("<Button-1>", lambda e, fid=folder_id: self._select_folder(fid))

        for widget in [frame, lbl]:
            widget.bind("<Button-1>", lambda e, fid=folder_id: self._select_folder(fid))

    def _render_companies(self):
        for w in self.company_inner.winfo_children():
            w.destroy()

        section_bg = T.SECTION_COMPANIES
        
        # "All" option
        all_frame = Frame(self.company_inner, bg=section_bg, cursor="hand2")
        all_frame.pack(fill=X, pady=2)
        lbl_all = Label(all_frame, text="All Companies", font=T.FONT_LABEL,
                        bg=section_bg, fg=T.TEXT_PRIMARY, anchor=W, padx=8, pady=4)
        lbl_all.pack(fill=X)
        for w in [all_frame, lbl_all]:
            w.bind("<Button-1>", lambda e: self._filter_by_company(None))

        for domain, info in sorted(self.companies.items(), key=lambda x: -x[1]["count"]):
            row = Frame(self.company_inner, bg=section_bg, cursor="hand2")
            row.pack(fill=X, pady=1)

            dot = Label(row, text="●", font=("Segoe UI", 9), fg=info["color"],
                        bg=section_bg)
            dot.pack(side=LEFT, padx=(8, 4))

            name_lbl = Label(row, text=info["name"], font=T.FONT_LABEL,
                             bg=section_bg, fg=T.TEXT_PRIMARY, anchor=W)
            name_lbl.pack(side=LEFT, fill=X, expand=True)

            count_lbl = Label(row, text=str(info["count"]), font=T.FONT_SMALL,
                              bg=section_bg, fg=T.TEXT_MUTED, padx=6)
            count_lbl.pack(side=RIGHT)

            for w in [row, dot, name_lbl, count_lbl]:
                w.bind("<Button-1>", lambda e, d=domain: self._filter_by_company(d))

            # Right-click context menu
            menu = Menu(self.root, tearoff=0, bg=T.BG_SURFACE, fg=T.TEXT_PRIMARY)
            menu.add_command(label="Rename...",
                             command=lambda d=domain: self._rename_company(d))
            for w in [row, dot, name_lbl, count_lbl]:
                w.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))

    def _render_email_list(self, filter_query=""):
        """Rebuild the filtered message list and draw visible rows via virtual scrolling."""
        if filter_query:
            self._filtered_messages = []
            for msg in self.messages:
                sender = msg.get("from", {}).get("emailAddress", {})
                sender_name = sender.get("name", sender.get("address", "Unknown"))
                subject = msg.get("subject", "(No Subject)")
                preview = msg.get("bodyPreview", "")[:80]
                searchable = f"{sender_name} {subject} {preview}".lower()
                if filter_query in searchable:
                    self._filtered_messages.append(msg)
        else:
            self._filtered_messages = list(self.messages)

        self._visible_start = 0
        self._draw_visible_rows()
        self._update_scrollbar()

        # Show load more button if we got a full page
        if len(self.messages) > 0 and len(self.messages) % 50 == 0:
            self.load_more_frame.pack(fill=X, pady=4)
            self.btn_load_more.pack(pady=4)
        else:
            self.load_more_frame.pack_forget()

        self.msg_count_var.set(f"{len(self.messages)} messages")

    def _draw_visible_rows(self):
        """Draw only the visible rows on the canvas (virtual scrolling) - Paper Studio style."""
        self.list_canvas.delete("all")
        self._canvas_items.clear()

        canvas_width = self.list_canvas.winfo_width()
        if canvas_width < 10:
            canvas_width = 400

        end = min(self._visible_start + self._visible_count, len(self._filtered_messages))
        selected_id = self.current_message["id"] if self.current_message else None

        for draw_idx, msg_idx in enumerate(range(self._visible_start, end)):
            msg = self._filtered_messages[msg_idx]
            y = draw_idx * self._row_height

            sender = msg.get("from", {}).get("emailAddress", {})
            sender_name = sender.get("name", sender.get("address", "Unknown"))
            subject = msg.get("subject", "(No Subject)")
            preview = msg.get("bodyPreview", "")[:80]
            date_str = format_date(msg.get("receivedDateTime", ""))
            is_read = msg.get("isRead", True)
            has_att = msg.get("hasAttachments", False)

            company = self._get_company_for_msg(msg)
            border_color = company["color"] if company else T.BORDER
            is_selected = msg["id"] == selected_id

            items = []

            # Background - subtle selection/unread highlight (2025 trend: pastel tint for emphasis)
            if is_selected:
                bg_color = T.ACCENT_LIGHT
            elif not is_read:
                bg_color = T.HIGHLIGHT_LIGHT  # Warm butter cream for unread
            else:
                bg_color = T.BG_BASE
            items.append(self.list_canvas.create_rectangle(
                0, y, canvas_width, y + self._row_height - 1,
                fill=bg_color, outline="", tags="row"))

            # Left color border (accent for selected/unread, company color otherwise)
            if is_selected:
                left_border = T.ACCENT
            elif not is_read:
                left_border = T.HIGHLIGHT  # Butter yellow for unread indicator
            else:
                left_border = border_color
            items.append(self.list_canvas.create_rectangle(
                0, y, 4, y + self._row_height - 1,
                fill=left_border, outline="", tags="row"))

            # Unread indicator dot
            if not is_read:
                items.append(self.list_canvas.create_oval(
                    10, y + 12, 18, y + 20,
                    fill=T.ACCENT, outline="", tags="row"))

            # Sender name
            sender_font = T.FONT_SUBJECT if not is_read else T.FONT_LABEL
            sender_fg = T.TEXT_PRIMARY if not is_read else T.TEXT_SECONDARY
            sender_x = 24 if not is_read else 14
            items.append(self.list_canvas.create_text(
                sender_x, y + 12, text=sender_name, font=sender_font, fill=sender_fg,
                anchor=NW, tags="row"))

            # Date (right aligned)
            date_text = date_str
            if has_att:
                date_text = "📎 " + date_text
            items.append(self.list_canvas.create_text(
                canvas_width - 12, y + 12, text=date_text, font=T.FONT_SMALL,
                fill=T.TEXT_MUTED, anchor="ne", tags="row"))

            # Subject
            subj_font = T.FONT_SUBJECT if not is_read else T.FONT_LABEL
            subj_fg = T.TEXT_PRIMARY if not is_read else T.TEXT_SECONDARY
            max_subj_len = max(20, (canvas_width - 30) // 7)
            subj_display = subject[:max_subj_len] + ("..." if len(subject) > max_subj_len else "")
            items.append(self.list_canvas.create_text(
                14, y + 32, text=subj_display, font=subj_font, fill=subj_fg,
                anchor=NW, tags="row"))

            # Preview
            max_prev_len = max(20, (canvas_width - 30) // 6)
            prev_display = preview[:max_prev_len] + ("..." if len(preview) > max_prev_len else "")
            items.append(self.list_canvas.create_text(
                14, y + 52, text=prev_display, font=T.FONT_SMALL, fill=T.TEXT_MUTED,
                anchor=NW, tags="row"))

            # Separator line (subtle)
            items.append(self.list_canvas.create_line(
                12, y + self._row_height - 1, canvas_width - 12, y + self._row_height - 1,
                fill=T.BORDER, tags="row"))

            self._canvas_items[msg_idx] = items

    def _update_row_read_status(self, msg_id):
        """Update a single row's visual appearance when read status changes.
        Redraws only visible rows if the message is currently visible."""
        # Check if this message is currently visible
        for msg_idx in range(self._visible_start,
                             min(self._visible_start + self._visible_count,
                                 len(self._filtered_messages))):
            if self._filtered_messages[msg_idx]["id"] == msg_id:
                self._draw_visible_rows()
                return

    def _select_message(self, msg):
        """Select and preview an email."""
        self.current_message = msg
        msg_id = msg["id"]

        # Check memory cache first -- instant preview
        if msg_id in self.message_cache:
            full_msg = self.message_cache[msg_id]
            if not msg.get("isRead"):
                msg["isRead"] = True
                try:
                    self.cache.update_read_status(msg_id, True)
                except Exception:
                    pass
                threading.Thread(target=lambda: self._mark_read_bg(msg_id), daemon=True).start()
            # Single draw covers both selection highlight and read status change
            self._draw_visible_rows()
            self._show_preview(full_msg)
            self._prefetch_adjacent(msg)
            return

        # Check SQLite cache for body
        try:
            cached_body = self.cache.get_message_body(msg_id)
        except Exception:
            cached_body = None
        
        if cached_body:
            # Reconstruct full message from list data + cached body
            full_msg = dict(msg)
            full_msg["body"] = cached_body
            self.message_cache[msg_id] = full_msg
            if not msg.get("isRead"):
                msg["isRead"] = True
                try:
                    self.cache.update_read_status(msg_id, True)
                except Exception:
                    pass
                threading.Thread(target=lambda: self._mark_read_bg(msg_id), daemon=True).start()
            self._draw_visible_rows()
            self._show_preview(full_msg)
            self._prefetch_adjacent(msg)
            return

        # Show instant preview from list data while full body loads
        self._show_instant_preview(msg)

        # Mark read in parallel with fetching full body (don't block on it)
        if not msg.get("isRead"):
            msg["isRead"] = True
            try:
                self.cache.update_read_status(msg_id, True)
            except Exception:
                pass
            threading.Thread(target=lambda: self._mark_read_bg(msg_id), daemon=True).start()
        # Single draw covers both selection highlight and read status change
        self._draw_visible_rows()

        def load_full():
            try:
                full_msg = self.graph.get_message(msg_id)
                self.message_cache[msg_id] = full_msg
                # Only update preview if this message is still selected
                self.root.after(0, lambda: self._show_preview_if_current(full_msg, msg_id))
                self._prefetch_adjacent_bg(msg)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error loading message: {e}"))

        threading.Thread(target=load_full, daemon=True).start()

    def _show_instant_preview(self, msg):
        """Show a quick preview from list data while full body loads."""
        sender = msg.get("from", {}).get("emailAddress", {})
        self.preview_from.config(text=f'From: {sender.get("name", "")} <{sender.get("address", "")}>')
        self.preview_subject.config(text=msg.get("subject", "(No Subject)"))
        self.preview_date.config(text=format_date(msg.get("receivedDateTime", "")))
        self.preview_to.config(text="")

        # Build a rich placeholder while full body loads.
        self._raw_html_content = wrap_plain_text_as_html(msg.get("bodyPreview", "Loading..."))
        self._plain_fallback_content = msg.get("bodyPreview", "Loading...")

        # Use bodyPreview (already available from list data) as placeholder
        preview_text = msg.get("bodyPreview", "Loading...")
        loading_html = (
            "<html><body><p style='color: #888; font-family: Segoe UI;'>"
            "Loading email content...</p></body></html>"
        )
        if self._ensure_browser_controller(notify=False):
            try:
                self._activate_email_rich_view()
                self._browser_controller.load_html(loading_html)
            except Exception:
                self._show_plain_fallback(preview_text, "Rich preview failed; using plain fallback")
        else:
            self._show_plain_fallback(preview_text, "Rich preview unavailable; using plain fallback")

        # Hide attachments while loading
        for w in self.att_frame.winfo_children():
            w.destroy()
        self.att_frame.pack_forget()

    def _show_preview_if_current(self, full_msg, msg_id):
        """Only update preview if the user hasn't clicked a different email."""
        if self.current_message and self.current_message.get("id") == msg_id:
            self._show_preview(full_msg)

    def _mark_read_bg(self, msg_id):
        """Mark message as read in background (fire-and-forget)."""
        try:
            self.graph.mark_read(msg_id)
        except Exception:
            pass

    def _prefetch_adjacent(self, msg):
        """Prefetch adjacent messages in background."""
        threading.Thread(target=lambda: self._prefetch_adjacent_bg(msg), daemon=True).start()

    def _prefetch_adjacent_bg(self, msg):
        """Background worker to prefetch N-1 and N+1 messages."""
        try:
            idx = None
            for i, m in enumerate(self.messages):
                if m["id"] == msg["id"]:
                    idx = i
                    break
            if idx is None:
                return
            for adj_idx in [idx - 1, idx + 1]:
                if 0 <= adj_idx < len(self.messages):
                    adj_id = self.messages[adj_idx]["id"]
                    if adj_id not in self.message_cache:
                        try:
                            full = self.graph.get_message(adj_id)
                            self.message_cache[adj_id] = full
                        except Exception:
                            pass
        except Exception:
            pass

    def _show_preview(self, msg):
        """Display email in preview panel."""
        sender = msg.get("from", {}).get("emailAddress", {})
        self.preview_from.config(text=f'From: {sender.get("name", "")} <{sender.get("address", "")}>')
        self.preview_subject.config(text=msg.get("subject", "(No Subject)"))
        self.preview_date.config(text=format_date(msg.get("receivedDateTime", "")))

        to_list = msg.get("toRecipients", [])
        to_str = ", ".join(r.get("emailAddress", {}).get("address", "") for r in to_list)
        cc_list = msg.get("ccRecipients", [])
        if cc_list:
            cc_str = ", ".join(r.get("emailAddress", {}).get("address", "") for r in cc_list)
            to_str += f"  CC: {cc_str}"
        self.preview_to.config(text=f"To: {to_str}")

        # Body
        body = msg.get("body", {})
        raw_content = body.get("content", "")
        content_type = body.get("contentType", "")
        
        # Prepare rich-first + plain fallback payloads.
        if content_type.lower() == "html":
            self._raw_html_content = raw_content
            plain_content = strip_html(raw_content)
        else:
            self._raw_html_content = wrap_plain_text_as_html(raw_content)
            plain_content = raw_content
        self._plain_fallback_content = plain_content

        # Cache the message body for offline access
        if raw_content and not msg.get("_fromCache"):
            try:
                self.cache.save_message_body(msg["id"], content_type, raw_content)
            except Exception:
                pass

        # Rich-first view with automatic plain fallback.
        self.current_message = msg
        self._render_html_preview()

        # Attachments
        for w in self.att_frame.winfo_children():
            w.destroy()

        msg_id = msg["id"]
        cloud_links = collect_cloud_pdf_links(
            raw_content if content_type.lower() == "html" else "",
            plain_content,
        )
        self.cloud_link_cache[msg_id] = cloud_links

        has_file_attachments = bool(msg.get("hasAttachments"))
        has_cloud_links = bool(cloud_links)

        if has_file_attachments or has_cloud_links:
            self.att_frame.pack(fill=X, before=self.email_action_frame)
            if has_file_attachments:
                Label(
                    self.att_frame,
                    text="ATTACHMENTS",
                    font=("Segoe UI", 8, "bold"),
                    bg=COLOR_BG_LIGHT,
                    fg=COLOR_BORDER,
                ).pack(anchor=W, pady=(0, 4))

                # Check attachment cache first (memory then SQLite)
                if msg_id in self.attachment_cache:
                    self._render_attachments(self.attachment_cache[msg_id], msg_id)
                else:
                    # Try SQLite cache
                    cached_atts = self.cache.get_attachments(msg_id)
                    if cached_atts:
                        self.attachment_cache[msg_id] = cached_atts
                        self._render_attachments(cached_atts, msg_id)
                    else:
                        def load_atts():
                            try:
                                atts = self.graph.get_attachments(msg_id)
                                self.attachment_cache[msg_id] = atts
                                # Save to SQLite cache
                                try:
                                    self.cache.save_attachments(msg_id, atts)
                                except Exception:
                                    pass
                                self.root.after(0, lambda: self._render_attachments(atts, msg_id))
                            except Exception:
                                pass

                        threading.Thread(target=load_atts, daemon=True).start()

            if has_cloud_links:
                self._render_cloud_pdf_links(msg_id, cloud_links)
        else:
            self.att_frame.pack_forget()

    def _render_attachments(self, attachments, msg_id):
        for att in attachments:
            if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            att_row = Frame(self.att_frame, bg=COLOR_BG_LIGHT)
            att_row.pack(fill=X, pady=2)

            name = att.get("name", "file")
            size = format_size(att.get("size", 0))
            Label(att_row, text=f"\U0001F4CE {name}", font=FONT_NORMAL,
                  bg=COLOR_BG_LIGHT, fg=COLOR_TEXT).pack(side=LEFT)
            Label(att_row, text=size, font=FONT_SMALL,
                  bg=COLOR_BG_LIGHT, fg=COLOR_READ).pack(side=LEFT, padx=(8, 0))

            is_pdf = name.lower().endswith(".pdf") or (att.get("contentType", "") or "").lower() == "application/pdf"
            if is_pdf:
                Button(att_row, text="View", font=FONT_SMALL, relief=FLAT,
                       bg=COLOR_BG_LIGHT, fg=COLOR_ACCENT,
                       command=lambda a=att, mid=msg_id: self._view_pdf_attachment(a, mid)
                       ).pack(side=RIGHT, padx=(0, 6))
            Button(att_row, text="Save", font=FONT_SMALL, relief=FLAT,
                   bg=COLOR_ACCENT, fg="white",
                   command=lambda a=att, mid=msg_id: self._save_attachment(a, mid)
                   ).pack(side=RIGHT)

    def _render_cloud_pdf_links(self, msg_id, links):
        if self.att_frame.winfo_children():
            Frame(self.att_frame, bg=COLOR_BORDER, height=1).pack(fill=X, pady=(6, 6))

        Label(
            self.att_frame,
            text="LINKED CLOUD FILES",
            font=("Segoe UI", 8, "bold"),
            bg=COLOR_BG_LIGHT,
            fg=COLOR_BORDER,
        ).pack(anchor=W, pady=(0, 4))

        summary = f"{len(links)} link(s) found in this email body."
        if links:
            sources = sorted({link.get("source", "External") for link in links})
            summary += " Sources: " + ", ".join(sources[:3]) + ("..." if len(sources) > 3 else "")

        row = Frame(self.att_frame, bg=COLOR_BG_LIGHT)
        row.pack(fill=X, pady=(0, 2))
        Label(row, text=summary, font=FONT_SMALL, bg=COLOR_BG_LIGHT, fg=COLOR_READ).pack(side=LEFT)
        Button(
            row,
            text="Select & Open PDFs",
            font=FONT_SMALL,
            relief=FLAT,
            bg=COLOR_ACCENT,
            fg="white",
            command=lambda mid=msg_id: self._open_cloud_pdf_links(mid),
        ).pack(side=RIGHT)

    def _open_cloud_pdf_links(self, msg_id):
        links = self.cloud_link_cache.get(msg_id) or []
        if not links:
            messagebox.showinfo("No Links", "No supported cloud links found in this email.", parent=self.root)
            return

        picker = CloudPdfLinkDialog(self.root, links)
        selected_links = picker.show()
        if not selected_links:
            return

        self.status_var.set(f"Downloading {len(selected_links)} linked PDF(s)...")

        def do_fetch():
            opened = 0
            failures = []
            for index, link in enumerate(selected_links, start=1):
                try:
                    content = self._download_linked_pdf_bytes(link["download_url"])
                    name = link.get("suggested_name") or f"linked_{index}.pdf"
                    digest = hashlib.sha1(link["download_url"].encode("utf-8")).hexdigest()[:12]
                    doc_key = f"link:{msg_id}:{digest}"
                    self.root.after(
                        0,
                        lambda dk=doc_key, nm=name, blob=content: self._open_pdf_in_tab(
                            doc_key=dk,
                            name=nm,
                            content=blob,
                            new_tab=True,
                        ),
                    )
                    opened += 1
                except Exception as exc:
                    failures.append(f"{link.get('source', 'External')}: {exc}")

            def show_result():
                if opened:
                    self.status_var.set(f"Opened {opened} linked PDF(s)")
                else:
                    self.status_var.set("No linked PDFs opened")
                if failures:
                    messagebox.showwarning(
                        "Some Links Failed",
                        "Could not open all selected links:\n\n" + "\n".join(failures[:6]),
                        parent=self.root,
                    )

            self.root.after(0, show_result)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _download_linked_pdf_bytes(self, url):
        result = download_url_content(url)
        if not result.content:
            raise BrowserDownloadError("Downloaded file is empty.")
        return require_pdf_bytes(result)

    def _open_pdf_in_tab(self, doc_key, name, content, new_tab=False):
        if not new_tab or not hasattr(self, "pdf_tabs_notebook"):
            self.pdf_viewer.load_pdf_bytes(doc_key, name, content)
            self.preview_notebook.select(self.pdf_tab)
            if hasattr(self, "pdf_tabs_notebook") and hasattr(self, "_pdf_main_tab"):
                self.pdf_tabs_notebook.select(self._pdf_main_tab)
            return

        existing = self._pdf_extra_tabs.get(doc_key)
        if existing is None:
            tab_frame = Frame(self.pdf_tabs_notebook, bg=T.BG_SURFACE)
            viewer = self._pdf_viewer_cls(
                tab_frame,
                config_get=self.config.get,
                config_set=self.config.set,
                initial_dir=PDF_DIR,
                bg=T.BG_SURFACE,
                accent=T.ACCENT,
            )
            viewer.pack(fill=BOTH, expand=True)
            tab_label = name if len(name) <= 24 else name[:21] + "..."
            self.pdf_tabs_notebook.add(tab_frame, text=tab_label)
            existing = {"frame": tab_frame, "viewer": viewer}
            self._pdf_extra_tabs[doc_key] = existing

        existing["viewer"].load_pdf_bytes(doc_key, name, content)
        self.preview_notebook.select(self.pdf_tab)
        self.pdf_tabs_notebook.select(existing["frame"])

    def _close_current_pdf_tab(self):
        if not hasattr(self, "pdf_tabs_notebook"):
            return
        current_tab = self.pdf_tabs_notebook.select()
        if not current_tab:
            return
        if hasattr(self, "_pdf_main_tab") and str(current_tab) == str(self._pdf_main_tab):
            return

        for key, info in list(self._pdf_extra_tabs.items()):
            if str(info["frame"]) == str(current_tab):
                del self._pdf_extra_tabs[key]
                break

        self.pdf_tabs_notebook.forget(current_tab)
        if hasattr(self, "_pdf_main_tab"):
            self.pdf_tabs_notebook.select(self._pdf_main_tab)

    def _view_pdf_attachment(self, att, msg_id):
        """Download a PDF attachment and open it in the embedded PDF tab (no disk write)."""
        name = att.get("name", "attachment.pdf")
        self.status_var.set(f"Loading PDF: {name} ...")

        def do_open():
            try:
                data = self.graph.download_attachment(msg_id, att["id"])
                b64 = data.get("contentBytes", "")
                if not b64:
                    raise RuntimeError("Attachment content missing (no contentBytes).")
                content = base64.b64decode(b64)
                doc_key = f"graph:{msg_id}:{att['id']}:{att.get('size', 0)}"

                def on_ui():
                    try:
                        self._open_pdf_in_tab(doc_key=doc_key, name=name, content=content, new_tab=False)
                        self.status_var.set(f"PDF opened: {name}")
                    except Exception as e:
                        messagebox.showerror("PDF Error", str(e), parent=self.root)

                self.root.after(0, on_ui)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("PDF Error", str(e), parent=self.root))

        threading.Thread(target=do_open, daemon=True).start()

    def _save_attachment(self, att, msg_id):
        save_path = filedialog.asksaveasfilename(
            title="Save Attachment",
            initialfile=att.get("name", "file"))
        if not save_path:
            return

        def do_save():
            try:
                data = self.graph.download_attachment(msg_id, att["id"])
                content = base64.b64decode(data.get("contentBytes", ""))
                with open(save_path, 'wb') as f:
                    f.write(content)
                self.root.after(0, lambda: self.status_var.set(f"Saved: {os.path.basename(save_path)}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Save Error", str(e)))

        threading.Thread(target=do_save, daemon=True).start()

    # -- Actions --

    def _select_folder(self, folder_id):
        self.current_folder = folder_id
        self.search_query = ""
        self.messages = []
        self._load_messages()
        self._load_folders()  # Refresh to update active highlighting

    def _filter_by_company(self, domain):
        """Filter email list by company domain - searches full SQLite cache."""
        if domain is None:
            self._render_email_list()
            return

        # Search full cache for ALL emails from this domain
        try:
            cached_msgs = self.cache.search_by_domain(domain)
        except Exception:
            cached_msgs = None
        
        if cached_msgs:
            self._filtered_messages = cached_msgs
        else:
            # Fallback to in-memory filter
            self._filtered_messages = []
            for msg in self.messages:
                sender = msg.get("from", {}).get("emailAddress", {})
                address = sender.get("address", "")
                if "@" in address and address.split("@")[1].lower() == domain:
                    self._filtered_messages.append(msg)

        self._visible_start = 0
        self._draw_visible_rows()
        self._update_scrollbar()
        self.msg_count_var.set(f"{len(self._filtered_messages)} messages from @{domain}")

    def _rename_company(self, domain):
        """Rename a company via dialog."""
        current_name = self.companies.get(domain, {}).get("name", domain)
        win = Toplevel(self.root)
        win.title("Rename Company")
        win.geometry("350x120")
        win.transient(self.root)
        win.grab_set()

        Frame(win, bg=COLOR_BG_WHITE).pack(fill=BOTH, expand=True)
        f = Frame(win, bg=COLOR_BG_WHITE, padx=15, pady=15)
        f.pack(fill=BOTH, expand=True)

        Label(f, text=f"Rename '{current_name}' ({domain}):", font=FONT_NORMAL,
              bg=COLOR_BG_WHITE).pack(anchor=W)
        name_var = StringVar(value=current_name)
        Entry(f, textvariable=name_var, font=FONT_NORMAL).pack(fill=X, pady=(4, 8))

        def save():
            new_name = name_var.get().strip()
            if new_name:
                companies = self.config.get("companies", {})
                companies[domain] = new_name
                self.config.set("companies", companies)
                self.companies[domain]["name"] = new_name
                self._render_companies()
            win.destroy()

        Button(f, text="Save", font=FONT_NORMAL, bg=COLOR_ACCENT, fg="white",
               relief=FLAT, command=save).pack(side=RIGHT)

    def _compose(self, mode="new"):
        reply_msg = self.current_message if mode in ("reply", "reply_all", "forward") else None
        ComposeWindow(
            self.root,
            self.graph,
            mode=mode,
            reply_msg=reply_msg,
            user_email=self.user_email,
            on_sent=lambda: self._load_messages(),
            config=self.config,
            status_callback=lambda message: self.status_var.set(message),
        )

    def _open_attachment_browser(self):
        AttachmentBrowser(self.root, self.all_messages, self.graph,
                          attachment_cache=self.attachment_cache)

    def _open_company_manager(self):
        """Open the company manager dialog."""
        def on_update():
            # Refresh company sidebar after labels change
            self._detect_companies()
            self._render_companies()
        CompanyManagerDialog(self.root, self.cache, self.config, on_update=on_update)

    def _reconnect(self):
        if self.graph is not None:
            self.graph.clear_cached_tokens()
        else:
            cid = (self.config.get("client_id") or "").strip() or DEFAULT_CLIENT_ID
            cache_file = token_cache_path_for_client_id(cid)
            if os.path.exists(cache_file):
                os.remove(cache_file)
        self._connect()

    # -- Polling --

    def _start_polling(self):
        # Initialize known_ids from current messages
        self.known_ids = {m["id"] for m in self.messages}
        # Get initial delta token for efficient polling
        self._init_delta_token()
        self._poll()

    def _init_delta_token(self):
        """Initialize delta token for inbox if not already cached."""
        def do_init():
            try:
                if self.sync_service:
                    delta_link = self.sync_service.initialize_delta_token(folder_id="inbox")
                    if delta_link:
                        print("[DELTA] Initialized delta token for inbox")
            except Exception as e:
                print(f"[DELTA] Error initializing delta token: {e}")
        
        threading.Thread(target=do_init, daemon=True).start()

    def _poll(self):
        if not self.graph or not self.graph.access_token:
            return

        if not self._poll_lock.acquire(blocking=False):
            self._poll_id = self.root.after(POLL_INTERVAL_MS, self._poll)
            return

        def do_poll():
            try:
                msgs = []
                deleted = []
                if self.sync_service:
                    msgs, deleted = self.sync_service.sync_delta_once(folder_id="inbox", fallback_top=10)
                else:
                    msgs, _ = self.graph.get_messages(folder_id="inbox", top=10)

                if deleted:
                    self.root.after(0, lambda ids=deleted: self._handle_deleted(ids))

                self._poll_failures = 0  # Reset backoff on success

                new_msgs = collect_new_unread(msgs, self.known_ids)

                if new_msgs and self.current_folder == "inbox":
                    self.root.after(0, lambda: self._on_new_mail(new_msgs, len(new_msgs)))

                now = datetime.now().strftime("%I:%M %p").lstrip('0')
                self.root.after(0, lambda: self.sync_var.set(f"Last sync: {now}"))
            except Exception as e:
                print(f"[POLL] Error: {e}")
                self._poll_failures += 1
            finally:
                self._poll_lock.release()

        threading.Thread(target=do_poll, daemon=True).start()
        # Exponential backoff on failures: 30s, 60s, 120s, max 5min
        backoff = min(POLL_INTERVAL_MS * (2 ** self._poll_failures), 300000)
        self._poll_id = self.root.after(backoff, self._poll)

    def _handle_deleted(self, deleted_ids):
        """Remove deleted messages from in-memory lists."""
        deleted_set = set(deleted_ids)
        self.messages = [m for m in self.messages if m["id"] not in deleted_set]
        self.all_messages = [m for m in self.all_messages if m["id"] not in deleted_set]
        self.known_ids -= deleted_set
        # Remove from memory caches
        for mid in deleted_ids:
            self.message_cache.pop(mid, None)
            self.attachment_cache.pop(mid, None)
            self.cloud_link_cache.pop(mid, None)
        # Refresh display if needed
        if self.current_folder == "inbox":
            self._render_email_list()

    def _on_new_mail(self, new_msgs, count):
        # Prepend new messages instead of full reload
        existing_ids = {m["id"] for m in self.messages}
        all_msg_ids = {am["id"] for am in self.all_messages}
        prepended = False
        for m in reversed(new_msgs):
            if m["id"] not in existing_ids:
                self.messages.insert(0, m)
                existing_ids.add(m["id"])
                # Also update all_messages cache
                if m["id"] not in all_msg_ids:
                    self.all_messages.append(m)
                    all_msg_ids.add(m["id"])
                prepended = True

        if prepended:
            # Re-apply active filter instead of resetting it
            filter_query = self.list_search_var.get().strip().lower()
            if filter_query == "filter list...":
                filter_query = ""
            self._render_email_list(filter_query)
            self._detect_companies()
            self._render_companies()
            self._update_status()

        # Desktop notification
        if HAS_WINOTIFY and new_msgs:
            try:
                sender = new_msgs[0].get("from", {}).get("emailAddress", {})
                toast = Notification(
                    app_id=APP_NAME,
                    title=f"{count} new email(s)",
                    msg=f"From: {sender.get('name', sender.get('address', ''))}\n"
                        f"{new_msgs[0].get('subject', '')}",
                )
                toast.show()
            except Exception:
                pass

    def _update_status(self):
        now = datetime.now().strftime("%I:%M %p").lstrip('0')
        self.sync_var.set(f"Last sync: {now}")

    def on_close(self):
        """Save window geometry on close."""
        self.config.set("window_geometry", self.root.geometry())
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
        if self._browser_controller is not None:
            self._browser_controller.dispose()
        if self._browser_tab_controller is not None:
            self._browser_tab_controller.dispose()
        self.root.destroy()


def main():
    root = Tk()
    root.withdraw()  # Hide main window during splash

    # Build the app while splash plays (auth starts in background)
    app = EmailApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)

    def on_splash_done():
        root.deiconify()
        root.lift()
        root.focus_force()

    SplashScreen(root, on_complete=on_splash_done)
    root.mainloop()


if __name__ == "__main__":
    main()

