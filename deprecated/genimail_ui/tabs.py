from tkinter import (
    BOTTOM,
    BOTH,
    FLAT,
    LEFT,
    RIGHT,
    VERTICAL,
    WORD,
    X,
    Frame,
    Label,
    Scrollbar,
    StringVar,
    Text,
)
from tkinter import ttk
import os

from genimail.ui.theme import T
from genimail.ui.widgets import WarmButton


def build_preview_tabs(app, pdf_viewer_cls, scanner_cls, pdf_initial_dir):
    """Build the email/pdf/scan/browser notebook tabs for the preview panel."""
    app.preview_notebook = ttk.Notebook(app.preview_panel)
    app.preview_notebook.pack(fill=BOTH, expand=True)

    app.email_tab = Frame(app.preview_notebook, bg=T.BG_SURFACE)
    app.pdf_tab = Frame(app.preview_notebook, bg=T.BG_SURFACE)
    app.scan_tab = Frame(app.preview_notebook, bg=T.BG_SURFACE)
    app.browser_tab = Frame(app.preview_notebook, bg=T.BG_SURFACE)
    app.preview_notebook.add(app.email_tab, text="Email")
    app.preview_notebook.add(app.pdf_tab, text="PDF")
    app.preview_notebook.add(app.scan_tab, text="Scan")
    app.preview_notebook.add(app.browser_tab, text="Browser")

    email_toolbar = Frame(app.email_tab, bg=T.BG_MUTED, padx=12, pady=6)
    email_toolbar.pack(fill=X)

    app._browser_controller = None
    app._browser_tab_controller = None
    app._raw_html_content = None
    app._plain_fallback_content = ""

    open_browser_lbl = Label(
        email_toolbar,
        text="Open Web Tab",
        font=T.FONT_SMALL,
        bg=T.BG_MUTED,
        fg=T.ACCENT,
        cursor="hand2",
    )
    open_browser_lbl.pack(side=RIGHT)
    open_browser_lbl.bind("<Button-1>", lambda e: app._open_in_browser())
    open_browser_lbl.bind("<Enter>", lambda e: open_browser_lbl.config(fg=T.ACCENT_HOVER))
    open_browser_lbl.bind("<Leave>", lambda e: open_browser_lbl.config(fg=T.ACCENT))

    app.body_container = Frame(app.email_tab, bg=T.BG_SURFACE)
    app.body_container.pack(fill=BOTH, expand=True)

    app.email_browser_host = Frame(app.body_container, bg=T.BG_SURFACE)
    app.email_browser_host.pack(fill=BOTH, expand=True)

    app.preview_fallback_frame = Frame(app.body_container, bg=T.BG_SURFACE)
    app.preview_body = Text(
        app.preview_fallback_frame,
        font=T.FONT_BODY,
        wrap=WORD,
        relief=FLAT,
        bg=T.BG_SURFACE,
        fg=T.TEXT_PRIMARY,
        padx=16,
        pady=12,
        state="disabled",
        cursor="arrow",
    )
    preview_sb = Scrollbar(app.preview_fallback_frame, orient=VERTICAL, command=app.preview_body.yview)
    app.preview_body.configure(yscrollcommand=preview_sb.set)
    app.preview_scrollbar = preview_sb
    preview_sb.pack(side=RIGHT, fill="y")
    app.preview_body.pack(fill=BOTH, expand=True)
    app.preview_fallback_frame.pack_forget()

    app.att_frame = Frame(app.email_tab, bg=T.BG_MUTED, padx=12, pady=8)

    app.email_action_frame = Frame(app.email_tab, bg=T.BG_MUTED, padx=12, pady=10)
    app.email_action_frame.pack(fill=X, side=BOTTOM)

    WarmButton(
        app.email_action_frame,
        "Reply",
        lambda: app._compose("reply"),
        primary=True,
        width=80,
        height=32,
        bg=T.BG_MUTED,
    ).pack(side=LEFT)
    WarmButton(
        app.email_action_frame,
        "Reply All",
        lambda: app._compose("reply_all"),
        primary=False,
        width=90,
        height=32,
        bg=T.BG_MUTED,
    ).pack(side=LEFT, padx=(8, 0))
    WarmButton(
        app.email_action_frame,
        "Forward",
        lambda: app._compose("forward"),
        primary=False,
        width=80,
        height=32,
        bg=T.BG_MUTED,
    ).pack(side=LEFT, padx=(8, 0))
    WarmButton(
        app.email_action_frame,
        "New Email",
        lambda: app._compose("new"),
        primary=True,
        width=100,
        height=32,
        bg=T.BG_MUTED,
    ).pack(side=RIGHT)

    pdf_toolbar = Frame(app.pdf_tab, bg=T.BG_MUTED, padx=12, pady=6)
    pdf_toolbar.pack(fill=X)
    Label(
        pdf_toolbar,
        text="PDF Tabs",
        font=T.FONT_SMALL,
        bg=T.BG_MUTED,
        fg=T.TEXT_SECONDARY,
    ).pack(side=LEFT)
    WarmButton(
        pdf_toolbar,
        "Close Current Tab",
        app._close_current_pdf_tab,
        primary=False,
        width=130,
        height=30,
        bg=T.BG_MUTED,
    ).pack(side=RIGHT)

    app.pdf_tabs_notebook = ttk.Notebook(app.pdf_tab)
    app.pdf_tabs_notebook.pack(fill=BOTH, expand=True)
    app._pdf_viewer_cls = pdf_viewer_cls
    app._pdf_extra_tabs = {}

    app._pdf_main_tab = Frame(app.pdf_tabs_notebook, bg=T.BG_SURFACE)
    app.pdf_tabs_notebook.add(app._pdf_main_tab, text="Current PDF")

    os.makedirs(pdf_initial_dir, exist_ok=True)
    app.pdf_viewer = pdf_viewer_cls(
        app._pdf_main_tab,
        config_get=app.config.get,
        config_set=app.config.set,
        initial_dir=pdf_initial_dir,
        bg=T.BG_SURFACE,
        accent=T.ACCENT,
    )
    app.pdf_viewer.pack(fill=BOTH, expand=True)

    if scanner_cls is None:
        Label(
            app.scan_tab,
            text="Scanner module unavailable.",
            font=T.FONT_BODY,
            bg=T.BG_SURFACE,
            fg=T.TEXT_SECONDARY,
        ).pack(padx=20, pady=20, anchor="nw")
    else:
        app.scan_tab.rowconfigure(0, weight=1)
        app.scan_tab.columnconfigure(0, weight=1)
        scan_host = Frame(app.scan_tab, bg=T.BG_SURFACE)
        scan_host.grid(row=0, column=0, sticky="nsew")
        app.scanner_app = scanner_cls(scan_host)

    browser_toolbar = Frame(app.browser_tab, bg=T.BG_MUTED, padx=8, pady=6)
    browser_toolbar.pack(fill=X)
    WarmButton(
        browser_toolbar,
        "Back",
        app._on_browser_back,
        primary=False,
        width=64,
        height=30,
        bg=T.BG_MUTED,
    ).pack(side=LEFT)
    WarmButton(
        browser_toolbar,
        "Forward",
        app._on_browser_forward,
        primary=False,
        width=76,
        height=30,
        bg=T.BG_MUTED,
    ).pack(side=LEFT, padx=(6, 0))
    WarmButton(
        browser_toolbar,
        "Reload",
        app._on_browser_reload,
        primary=False,
        width=70,
        height=30,
        bg=T.BG_MUTED,
    ).pack(side=LEFT, padx=(6, 8))

    app.browser_url_var = StringVar(value="https://")
    browser_url_entry = ttk.Entry(browser_toolbar, textvariable=app.browser_url_var)
    browser_url_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
    browser_url_entry.bind("<Return>", lambda e: app._on_browser_go())
    app.browser_url_entry = browser_url_entry

    WarmButton(
        browser_toolbar,
        "Go",
        app._on_browser_go,
        primary=True,
        width=48,
        height=30,
        bg=T.BG_MUTED,
    ).pack(side=RIGHT)

    app.browser_host = Frame(app.browser_tab, bg=T.BG_SURFACE)
    app.browser_host.pack(fill=BOTH, expand=True)

    app._activate_email_rich_view()
