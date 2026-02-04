"""
Genis Email Hub v2 - Paper Studio Edition
Outlook/Hotmail Email Client with warm, paper-inspired aesthetic.
Uses MSAL + Microsoft Graph API for authentication and email operations.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
import webbrowser
import html
import base64
from datetime import datetime
from tkinter import (
    Tk, Frame, Label, Entry, Text, Button, Scrollbar, Canvas,
    Toplevel, StringVar, messagebox, filedialog,
    Menu, VERTICAL, HORIZONTAL, BOTH, LEFT, RIGHT, BOTTOM,
    X, Y, W, E, NW, WORD, END, DISABLED, NORMAL, FLAT,
    font as tkfont
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
from genimail.domain.helpers import (
    domain_to_company,
    format_date,
    format_size,
    strip_html,
    token_cache_path_for_client_id,
)
from genimail.domain.quotes import (
    build_quote_context,
    create_quote_doc,
    latest_doc_file,
    open_document_file,
)
from genimail.infra.cache_store import EmailCache
from genimail.infra.config_store import Config
from genimail.infra.graph_client import GraphClient
from genimail.paths import (
    CONFIG_FILE,
    DEFAULT_QUOTE_TEMPLATE_FILE,
    PDF_DIR,
    QUOTE_DIR,
)
from genimail.services.mail_sync import MailSyncService, collect_new_unread
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
class DeviceCodeDialog:
    """Dialog showing device code for user to authenticate."""

    def __init__(self, parent):
        self.win = Toplevel(parent)
        self.win.title(f"{APP_NAME} - Sign In")
        self.win.geometry("480x300")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.attributes("-topmost", True)
        self.win.focus_force()
        self.win.lift()

        main = Frame(self.win, bg=COLOR_BG_WHITE)
        main.pack(fill=BOTH, expand=True)

        # Header
        hdr = Frame(main, bg=COLOR_ACCENT, height=50)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text=f"{APP_NAME} - Sign In", font=("Segoe UI", 13, "bold"),
              fg="white", bg=COLOR_ACCENT).pack(pady=12)

        body = Frame(main, bg=COLOR_BG_WHITE, padx=25, pady=20)
        body.pack(fill=BOTH, expand=True)

        self.status_label = Label(body, text="Starting sign-in...", font=FONT_NORMAL,
                                  bg=COLOR_BG_WHITE, fg=COLOR_TEXT, wraplength=420, justify=LEFT)
        self.status_label.pack(anchor=W, pady=(0, 15))

        # Code display (large, easy to read)
        self.code_var = StringVar(value="...")
        code_frame = Frame(body, bg=COLOR_BG_LIGHT, padx=20, pady=12)
        code_frame.pack(fill=X)
        Label(code_frame, text="Your code:", font=FONT_SMALL, bg=COLOR_BG_LIGHT,
              fg=COLOR_READ).pack(anchor=W)
        self.code_label = Label(code_frame, textvariable=self.code_var,
                                font=("Consolas", 22, "bold"), bg=COLOR_BG_LIGHT,
                                fg=COLOR_ACCENT)
        self.code_label.pack(anchor=W, pady=(4, 0))

        hint = Label(body, text="A browser window has opened. Paste this code there\n"
                                "and sign in with your Microsoft account.",
                     font=FONT_NORMAL, bg=COLOR_BG_WHITE, fg=COLOR_READ,
                     justify=LEFT, wraplength=420)
        hint.pack(anchor=W, pady=(15, 0))

        self.waiting_label = Label(body, text="Waiting for you to sign in...",
                                   font=("Segoe UI", 9, "italic"), bg=COLOR_BG_WHITE,
                                   fg=COLOR_READ)
        self.waiting_label.pack(anchor=W, pady=(10, 0))

    def show_code(self, flow):
        """Update dialog with the device code from MSAL."""
        code = flow.get("user_code", "???")
        self.code_var.set(code)
        self.status_label.config(text="Go to microsoft.com/devicelogin and enter this code:")

    def close(self):
        try:
            self.win.grab_release()
            self.win.destroy()
        except Exception:
            pass


class ComposeWindow:
    """Email compose / reply window - Paper Studio styling."""

    def __init__(
        self,
        parent,
        graph_client,
        mode="new",
        reply_msg=None,
        on_sent=None,
        config=None,
        status_callback=None,
    ):
        self.graph = graph_client
        self.mode = mode
        self.reply_msg = reply_msg
        self.on_sent = on_sent
        self.config = config
        self.status_callback = status_callback
        self.attachment_files = []
        self._attachment_keys = set()
        self.last_quote_path = None

        self.win = Toplevel(parent)
        self.win.title(f"{'Reply' if mode == 'reply' else 'Forward' if mode == 'forward' else 'New Email'}"
                       f" - {APP_NAME}")
        self.win.geometry("680x580")
        self.win.minsize(520, 420)
        self.win.configure(bg=T.BG_BASE)

        main = Frame(self.win, bg=T.BG_SURFACE)
        main.pack(fill=BOTH, expand=True, padx=2, pady=2)

        # Toolbar
        toolbar = Frame(main, bg=T.BG_MUTED, pady=10, padx=12)
        toolbar.pack(fill=X)

        self.send_btn = WarmButton(
            toolbar, "Send", self._send, primary=True, width=90, height=36, bg=T.BG_MUTED
        )
        self.send_btn.pack(side=LEFT)

        WarmButton(
            toolbar, "Attach", self._attach, primary=False, width=80, height=36, bg=T.BG_MUTED
        ).pack(side=LEFT, padx=(10, 0))
        WarmButton(
            toolbar, "Quote .doc", self._create_quote_doc, primary=False, width=95, height=36, bg=T.BG_MUTED
        ).pack(side=LEFT, padx=(8, 0))
        WarmButton(
            toolbar, "Attach Quote", self._attach_latest_quote, primary=False, width=110, height=36, bg=T.BG_MUTED
        ).pack(side=LEFT, padx=(8, 0))
        WarmButton(
            toolbar, "Template...", self._choose_quote_template, primary=False, width=95, height=36, bg=T.BG_MUTED
        ).pack(side=LEFT, padx=(8, 0))

        self.attach_label = Label(toolbar, text="", font=T.FONT_SMALL, bg=T.BG_MUTED,
                                  fg=T.TEXT_SECONDARY)
        self.attach_label.pack(side=LEFT, padx=(10, 0))

        # Fields
        fields = Frame(main, bg=T.BG_SURFACE, padx=16, pady=12)
        fields.pack(fill=X)

        # To
        row_to = Frame(fields, bg=T.BG_SURFACE)
        row_to.pack(fill=X, pady=4)
        Label(row_to, text="To:", font=T.FONT_LABEL, bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY,
              width=7, anchor=E).pack(side=LEFT)
        self.to_var = StringVar()
        Entry(row_to, textvariable=self.to_var, font=T.FONT_LABEL, bg=T.BG_INPUT,
              fg=T.TEXT_PRIMARY, relief=FLAT, highlightthickness=1,
              highlightbackground=T.BORDER).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        # CC
        row_cc = Frame(fields, bg=T.BG_SURFACE)
        row_cc.pack(fill=X, pady=4)
        Label(row_cc, text="CC:", font=T.FONT_LABEL, bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY,
              width=7, anchor=E).pack(side=LEFT)
        self.cc_var = StringVar()
        Entry(row_cc, textvariable=self.cc_var, font=T.FONT_LABEL, bg=T.BG_INPUT,
              fg=T.TEXT_PRIMARY, relief=FLAT, highlightthickness=1,
              highlightbackground=T.BORDER).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        # Subject
        row_subj = Frame(fields, bg=T.BG_SURFACE)
        row_subj.pack(fill=X, pady=4)
        Label(row_subj, text="Subject:", font=T.FONT_LABEL, bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY,
              width=7, anchor=E).pack(side=LEFT)
        self.subj_var = StringVar()
        Entry(row_subj, textvariable=self.subj_var, font=T.FONT_LABEL, bg=T.BG_INPUT,
              fg=T.TEXT_PRIMARY, relief=FLAT, highlightthickness=1,
              highlightbackground=T.BORDER).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        # Separator
        Frame(main, bg=T.BORDER, height=1).pack(fill=X)

        # Body
        body_frame = Frame(main, bg=T.BG_SURFACE)
        body_frame.pack(fill=BOTH, expand=True)

        self.body_text = Text(body_frame, font=T.FONT_BODY, wrap=WORD, relief=FLAT,
                              bg=T.BG_SURFACE, fg=T.TEXT_PRIMARY, padx=16, pady=12,
                              insertbackground=T.TEXT_PRIMARY)
        scrollbar = Scrollbar(body_frame, command=self.body_text.yview)
        self.body_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.body_text.pack(fill=BOTH, expand=True)

        # Pre-fill for reply/forward
        if reply_msg:
            sender = reply_msg.get("from", {}).get("emailAddress", {})
            if mode == "reply":
                self.to_var.set(sender.get("address", ""))
                subj = reply_msg.get("subject", "")
                if not subj.lower().startswith("re:"):
                    subj = f"Re: {subj}"
                self.subj_var.set(subj)
            elif mode == "forward":
                subj = reply_msg.get("subject", "")
                if not subj.lower().startswith("fw:") and not subj.lower().startswith("fwd:"):
                    subj = f"Fw: {subj}"
                self.subj_var.set(subj)

            # Quote original
            orig_date = format_date(reply_msg.get("receivedDateTime", ""))
            orig_from = f'{sender.get("name", "")} <{sender.get("address", "")}>'
            body_content = reply_msg.get("body", {}).get("content", "")
            if reply_msg.get("body", {}).get("contentType", "").lower() == "html":
                body_content = strip_html(body_content)
            quoted = f"\n\n--- Original Message ---\nFrom: {orig_from}\nDate: {orig_date}\n\n{body_content}"
            self.body_text.insert("1.0", quoted)
            self.body_text.mark_set("insert", "1.0")

    def _status(self, message: str):
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception:
                pass

    def _refresh_attachment_label(self):
        if not self.attachment_files:
            self.attach_label.config(text="")
            return
        names = [os.path.basename(f) for f in self.attachment_files]
        shown = ", ".join(names[:3])
        if len(names) > 3:
            shown += ", ..."
        self.attach_label.config(text=f"{len(names)} file(s): {shown}")

    def _add_attachment_path(self, path: str) -> bool:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in self._attachment_keys:
            return False
        self._attachment_keys.add(normalized)
        self.attachment_files.append(os.path.abspath(path))
        return True

    def _attach_files(self, files):
        added = 0
        for fpath in files:
            if self._add_attachment_path(fpath):
                added += 1
        self._refresh_attachment_label()
        return added

    def _attach(self):
        files = filedialog.askopenfilenames(title="Attach Files", parent=self.win)
        if not files:
            return
        added = self._attach_files(files)
        if added == 0:
            messagebox.showinfo("Already Attached", "Those files are already attached.", parent=self.win)

    def _quote_template_path(self) -> str:
        if self.config:
            configured = (self.config.get("quote_template_path") or "").strip()
            if configured:
                return configured
        return DEFAULT_QUOTE_TEMPLATE_FILE

    def _quote_output_dir(self) -> str:
        if self.config:
            configured = (self.config.get("quote_output_dir") or "").strip()
            if configured:
                return configured
        return QUOTE_DIR

    def _choose_quote_template(self):
        path = filedialog.askopenfilename(
            title="Select Quote Template",
            filetypes=[("Word/Text Templates", "*.doc *.txt"), ("All files", "*.*")],
            parent=self.win,
        )
        if not path:
            return
        if self.config:
            self.config.set("quote_template_path", path)
        self._status(f"Quote template set: {os.path.basename(path)}")
        messagebox.showinfo("Template Set", f"Using template:\n{path}", parent=self.win)

    def _create_quote_doc(self):
        template_path = self._quote_template_path()
        output_dir = self._quote_output_dir()
        context = build_quote_context(
            self.reply_msg,
            to_value=self.to_var.get().strip(),
            subject_value=self.subj_var.get().strip(),
        )
        try:
            quote_path = create_quote_doc(template_path, output_dir, context)
        except Exception as e:
            messagebox.showerror("Quote Draft Error", str(e), parent=self.win)
            return

        self.last_quote_path = quote_path
        self._status(f"Quote draft created: {os.path.basename(quote_path)}")

        opened = open_document_file(quote_path)
        if not opened:
            messagebox.showwarning(
                "Open Quote",
                f"Quote draft created, but could not auto-open it.\n\nFile:\n{quote_path}",
                parent=self.win,
            )

        if messagebox.askyesno(
            "Attach Quote",
            f"Quote draft ready:\n{quote_path}\n\nAttach it to this email now?",
            parent=self.win,
        ):
            self._attach_files([quote_path])

    def _attach_latest_quote(self):
        candidate = None
        if self.last_quote_path and os.path.exists(self.last_quote_path):
            candidate = self.last_quote_path
        else:
            candidate = latest_doc_file(self._quote_output_dir())

        if not candidate:
            messagebox.showinfo(
                "No Quote Found",
                "No .doc quote draft found yet.\nUse 'Quote .doc' first.",
                parent=self.win,
            )
            return

        if not os.path.exists(candidate):
            messagebox.showwarning("Quote Missing", f"File not found:\n{candidate}", parent=self.win)
            return

        if self._add_attachment_path(candidate):
            self._refresh_attachment_label()
            self._status(f"Attached quote: {os.path.basename(candidate)}")
        else:
            messagebox.showinfo("Already Attached", "That quote is already attached.", parent=self.win)

    def _send(self):
        to_str = self.to_var.get().strip()
        to_list = [a.strip() for a in to_str.replace(';', ',').split(',') if a.strip()]
        if not to_list:
            messagebox.showwarning("Missing Recipient", "Please enter at least one recipient.",
                                   parent=self.win)
            return
        cc_str = self.cc_var.get().strip()
        cc_list = [a.strip() for a in cc_str.replace(';', ',').split(',') if a.strip()] if cc_str else []
        subject = self.subj_var.get().strip()
        body = self.body_text.get("1.0", END).strip()

        if not subject:
            send_without_subject = messagebox.askyesno(
                "Empty Subject",
                "Send this email without a subject?",
                parent=self.win,
            )
            if not send_without_subject:
                return

        if not body:
            send_without_body = messagebox.askyesno(
                "Empty Body",
                "Send this email with an empty body?",
                parent=self.win,
            )
            if not send_without_body:
                return

        if "quote" in subject.lower() and not self.attachment_files:
            send_without_quote = messagebox.askyesno(
                "No Quote Attachment",
                "Subject mentions a quote but no attachment is added.\n\nSend anyway?",
                parent=self.win,
            )
            if not send_without_quote:
                return

        # Build attachments
        attachments = []
        for fpath in self.attachment_files:
            try:
                with open(fpath, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": os.path.basename(fpath),
                    "contentBytes": content,
                })
            except Exception as e:
                messagebox.showerror("Attachment Error", f"Could not read {fpath}:\n{e}",
                                     parent=self.win)
                return

        self.send_btn.set_disabled(True)
        self._status("Sending email...")

        # Send in background thread
        def do_send():
            try:
                reply_id = None
                if self.mode == "reply" and self.reply_msg:
                    reply_id = self.reply_msg.get("id")
                self.graph.send_mail(to_list, cc_list, subject, body,
                                     attachments or None, reply_id)
                self.win.after(0, self._on_send_success)
            except Exception as e:
                self.win.after(0, lambda msg=str(e): self._on_send_fail(msg))

        threading.Thread(target=do_send, daemon=True).start()

    def _on_send_fail(self, message: str):
        self.send_btn.set_disabled(False)
        self._status("Send failed")
        messagebox.showerror("Send Failed", message, parent=self.win)

    def _on_send_success(self):
        self._status("Email sent")
        if self.on_sent:
            self.on_sent()
        self.win.destroy()


class AttachmentBrowser:
    """Modal window for browsing all attachments."""

    def __init__(self, parent, all_messages, graph_client, attachment_cache=None):
        self.graph = graph_client
        self.attachment_cache = attachment_cache if attachment_cache is not None else {}
        self.win = Toplevel(parent)
        self.win.title(f"Attachment Browser - {APP_NAME}")
        self.win.geometry("750x500")
        self.win.minsize(600, 400)
        self.win.transient(parent)

        main = Frame(self.win, bg=COLOR_BG_WHITE)
        main.pack(fill=BOTH, expand=True)

        # Header
        hdr = Frame(main, bg=COLOR_BG_LIGHT, padx=10, pady=6)
        hdr.pack(fill=X)
        Label(hdr, text="All Attachments", font=FONT_HEADER, bg=COLOR_BG_LIGHT).pack(side=LEFT)

        self.status_lbl = Label(hdr, text="Loading...", font=FONT_SMALL, bg=COLOR_BG_LIGHT,
                                fg=COLOR_READ)
        self.status_lbl.pack(side=RIGHT)

        # Treeview
        cols = ("filename", "from", "date", "size")
        tree_frame = Frame(main, bg=COLOR_BG_WHITE)
        tree_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("filename", text="Filename")
        self.tree.heading("from", text="From")
        self.tree.heading("date", text="Date")
        self.tree.heading("size", text="Size")
        self.tree.column("filename", width=250)
        self.tree.column("from", width=200)
        self.tree.column("date", width=120)
        self.tree.column("size", width=80)

        vsb = Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)

        # Download button
        btn_frame = Frame(main, bg=COLOR_BG_WHITE, padx=10, pady=8)
        btn_frame.pack(fill=X)
        Button(btn_frame, text="Download Selected", font=FONT_NORMAL,
               bg=COLOR_ACCENT, fg="white", relief=FLAT,
               command=self._download_selected).pack(side=RIGHT)

        # Store attachment info
        self.att_data = []
        self._item_to_att = {}  # tree item iid -> att info dict

        # Load in background
        self.messages_with_att = [m for m in all_messages if m.get("hasAttachments")]
        threading.Thread(target=self._load_attachments, daemon=True).start()

    def _load_attachments(self):
        count = 0
        lock = threading.Lock()

        def fetch_one(msg):
            """Fetch attachments for a single message."""
            nonlocal count
            msg_id = msg["id"]
            try:
                # Use cache if available
                if msg_id in self.attachment_cache:
                    atts = self.attachment_cache[msg_id]
                else:
                    atts = self.graph.get_attachments(msg_id)
                    self.attachment_cache[msg_id] = atts

                sender = msg.get("from", {}).get("emailAddress", {})
                for att in atts:
                    if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
                        info = {
                            "name": att.get("name", "unknown"),
                            "from": sender.get("name", sender.get("address", "")),
                            "date": format_date(msg.get("receivedDateTime", "")),
                            "size": att.get("size", 0),
                            "msg_id": msg_id,
                            "att_id": att["id"],
                        }
                        with lock:
                            self.att_data.append(info)
                            count += 1
                        self.win.after(0, lambda i=info: self._insert_att_row(i))
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(fetch_one, self.messages_with_att)

        final_count = count
        self.win.after(0, lambda: self.status_lbl.config(
            text=f"{final_count} attachment(s) found"))

    def _insert_att_row(self, info):
        """Insert an attachment row into the tree and record the mapping."""
        item_id = self.tree.insert(
            "", END, values=(info["name"], info["from"], info["date"],
                             format_size(info["size"])))
        self._item_to_att[item_id] = info

    def _download_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select an attachment to download.",
                                parent=self.win)
            return
        # Look up by tree item iid (which stores att_data index) instead of tree position
        item = sel[0]
        try:
            info = self._item_to_att[item]
        except (KeyError, AttributeError):
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Attachment", initialfile=info["name"], parent=self.win)
        if not save_path:
            return

        def do_download():
            try:
                att = self.graph.download_attachment(info["msg_id"], info["att_id"])
                content = base64.b64decode(att.get("contentBytes", ""))
                with open(save_path, 'wb') as f:
                    f.write(content)
                self.win.after(0, lambda: messagebox.showinfo(
                    "Saved", f"Attachment saved to:\n{save_path}", parent=self.win))
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror(
                    "Download Error", str(e), parent=self.win))

        threading.Thread(target=do_download, daemon=True).start()


class CompanyManagerDialog:
    """Dialog to view and manage company labels for all email domains."""

    def __init__(self, parent, cache, config, on_update=None):
        self.cache = cache
        self.config = config
        self.on_update = on_update

        self.win = Toplevel(parent)
        self.win.title(f"Company Manager - {APP_NAME}")
        self.win.geometry("700x500")
        self.win.minsize(550, 400)
        self.win.transient(parent)

        main = Frame(self.win, bg=COLOR_BG_WHITE)
        main.pack(fill=BOTH, expand=True)

        # Header
        hdr = Frame(main, bg=COLOR_BG_LIGHT, padx=10, pady=8)
        hdr.pack(fill=X)
        Label(hdr, text="Company Manager", font=FONT_HEADER, bg=COLOR_BG_LIGHT).pack(side=LEFT)
        Label(hdr, text="Double-click a domain to assign a label",
              font=FONT_SMALL, bg=COLOR_BG_LIGHT, fg=COLOR_READ).pack(side=RIGHT)

        # Treeview
        cols = ("domain", "label", "count", "last_email")
        tree_frame = Frame(main, bg=COLOR_BG_WHITE)
        tree_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("domain", text="Domain")
        self.tree.heading("label", text="Company Label")
        self.tree.heading("count", text="Emails")
        self.tree.heading("last_email", text="Last Email")
        self.tree.column("domain", width=200)
        self.tree.column("label", width=180)
        self.tree.column("count", width=70, anchor="center")
        self.tree.column("last_email", width=100)

        vsb = Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)

        self.tree.bind("<Double-1>", self._on_double_click)

        # Buttons
        btn_frame = Frame(main, bg=COLOR_BG_WHITE, padx=10, pady=8)
        btn_frame.pack(fill=X)

        Button(btn_frame, text="Edit Label", font=FONT_NORMAL, bg=COLOR_ACCENT,
               fg="white", relief=FLAT, command=self._edit_selected).pack(side=LEFT)
        Button(btn_frame, text="Auto-Label Common", font=FONT_NORMAL, relief=FLAT,
               command=self._auto_label).pack(side=LEFT, padx=(8, 0))
        Button(btn_frame, text="Refresh", font=FONT_NORMAL, relief=FLAT,
               command=self._load_data).pack(side=RIGHT)

        self._load_data()

    def _load_data(self):
        """Load all domains from cache."""
        self.tree.delete(*self.tree.get_children())
        try:
            domains = self.cache.get_all_domains()
            for d in domains:
                label = d.get("company_label") or ""
                last = format_date(d.get("last_email") or "")
                self.tree.insert("", END, values=(
                    d["domain"], label, d["count"], last
                ), tags=("labeled" if label else "unlabeled",))
            self.tree.tag_configure("unlabeled", foreground=COLOR_READ)
        except Exception as e:
            print(f"[COMPANY] Error loading domains: {e}")

    def _on_double_click(self, event):
        self._edit_selected()

    def _edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a domain to edit.", parent=self.win)
            return

        values = self.tree.item(sel[0], "values")
        domain = values[0]
        current_label = values[1]

        # Edit dialog
        edit_win = Toplevel(self.win)
        edit_win.title(f"Label: {domain}")
        edit_win.geometry("350x130")
        edit_win.transient(self.win)
        edit_win.grab_set()

        f = Frame(edit_win, bg=COLOR_BG_WHITE, padx=15, pady=15)
        f.pack(fill=BOTH, expand=True)

        Label(f, text=f"Set company label for @{domain}:", font=FONT_NORMAL,
              bg=COLOR_BG_WHITE).pack(anchor=W)
        
        label_var = StringVar(value=current_label)
        entry = Entry(f, textvariable=label_var, font=FONT_NORMAL)
        entry.pack(fill=X, pady=(4, 12))
        entry.focus_set()
        entry.select_range(0, END)

        def save():
            new_label = label_var.get().strip()
            count = self.cache.label_domain(domain, new_label if new_label else None)
            # Also save to config for color persistence
            companies = self.config.get("companies", {})
            if new_label:
                companies[domain] = new_label
            elif domain in companies:
                del companies[domain]
            self.config.set("companies", companies)
            edit_win.destroy()
            self._load_data()
            if self.on_update:
                self.on_update()

        entry.bind("<Return>", lambda e: save())
        Button(f, text="Save", font=FONT_NORMAL, bg=COLOR_ACCENT, fg="white",
               relief=FLAT, command=save).pack(side=RIGHT)

    def _auto_label(self):
        """Auto-label common domains."""
        KNOWN_DOMAINS = {
            "amazon.com": "Amazon", "amazon.ca": "Amazon",
            "google.com": "Google", "gmail.com": "Gmail",
            "microsoft.com": "Microsoft", "outlook.com": "Outlook",
            "apple.com": "Apple", "icloud.com": "iCloud",
            "paypal.com": "PayPal", "paypal.ca": "PayPal",
            "facebook.com": "Facebook", "meta.com": "Meta",
            "twitter.com": "Twitter", "x.com": "X",
            "linkedin.com": "LinkedIn",
            "netflix.com": "Netflix",
            "spotify.com": "Spotify",
            "uber.com": "Uber", "ubereats.com": "Uber Eats",
            "doordash.com": "DoorDash",
            "shopify.com": "Shopify",
            "stripe.com": "Stripe",
            "github.com": "GitHub",
            "docusign.com": "DocuSign", "docusign.net": "DocuSign",
            "interac.ca": "Interac",
        }
        
        labeled_count = 0
        companies = self.config.get("companies", {})
        
        for domain, label in KNOWN_DOMAINS.items():
            count = self.cache.label_domain(domain, label)
            if count > 0:
                labeled_count += count
                companies[domain] = label
        
        self.config.set("companies", companies)
        self._load_data()
        if self.on_update:
            self.on_update()
        
        messagebox.showinfo("Auto-Label Complete",
                           f"Labeled {labeled_count} emails from known companies.",
                           parent=self.win)


from genimail.ui.dialogs import AttachmentBrowser, CompanyManagerDialog, ComposeWindow


class EmailApp:
    """Main email application."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.config = Config()
        self._config_load_error = self.config.load_error
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
        self._loading = False

        # Performance: caches
        self.message_cache = {}      # msg_id -> full message body + metadata
        self.attachment_cache = {}   # msg_id -> list of attachments
        self.known_ids = set()       # tracked message IDs for smarter polling
        self._poll_failures = 0      # consecutive poll failure count for backoff

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

    # -- HTML View Methods --

    def _switch_view_mode_v2(self):
        """Switch between plain text and HTML view (Paper Studio version)."""
        mode = (self.view_mode.get() or "").strip().lower()
        
        if mode == "plain":
            if self._html_frame is not None:
                self._html_frame.pack_forget()
            self.preview_scrollbar.pack(side=RIGHT, fill=Y)
            self.preview_body.pack(fill=BOTH, expand=True)
        else:  # HTML
            if not self._ensure_html_frame():
                self.view_mode.set("Plain")
                return
            self.preview_body.pack_forget()
            self.preview_scrollbar.pack_forget()
            self._html_frame.pack(fill=BOTH, expand=True)
            self._render_html_preview()

    def _ensure_html_frame(self):
        """Create HTML frame on first use (lazy loading)."""
        if self._html_frame is not None:
            return True
        try:
            from tkinterweb import HtmlFrame
            self._html_frame = HtmlFrame(self.body_container, messages_enabled=False,
                                          vertical_scrollbar=True)
            # Don't pack yet - only pack when HTML view selected
            return True
        except ImportError:
            messagebox.showinfo("Missing Package",
                "HTML view requires tkinterweb.\n\n"
                "Install with:\n  pip install tkinterweb\n\n"
                "Using plain text view instead.",
                parent=self.root)
            return False
        except Exception as e:
            print(f"[HTML] Error creating HtmlFrame: {e}")
            return False

    def _switch_view_mode(self):
        """Switch between plain text and HTML view."""
        self._switch_view_mode_v2()

    def _render_html_preview(self):
        """Render HTML content in the HTML frame."""
        if self._html_frame is None or not self.current_message:
            return
        
        # Use stored raw HTML content
        if self._raw_html_content:
            try:
                self._html_frame.load_html(self._raw_html_content)
            except Exception as e:
                print(f"[HTML] Render error: {e}")
                # Fall back to plain text
                self.view_mode.set("Plain")
                self._switch_view_mode_v2()
        else:
            # No HTML content, show plain text wrapped in HTML
            body_preview = self.current_message.get("bodyPreview", "")
            wrapped = f"<html><body><pre style='font-family: Segoe UI; white-space: pre-wrap;'>{html.escape(body_preview)}</pre></body></html>"
            try:
                self._html_frame.load_html(wrapped)
            except Exception:
                pass

    def _open_in_browser(self):
        """Open current email in system browser."""
        if not self.current_message:
            messagebox.showinfo("No Email", "Select an email first.", parent=self.root)
            return
        
        content = self._raw_html_content
        if not content:
            # Use plain text wrapped in HTML
            body_preview = self.current_message.get("bodyPreview", "")
            content = f"<html><body><pre>{html.escape(body_preview)}</pre></body></html>"
        
        # Save to temp file and open
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', 
                                              delete=False, encoding='utf-8') as f:
                f.write(content)
                temp_path = f.name
            webbrowser.open(f'file:///{temp_path}')
        except Exception as e:
            messagebox.showerror("Error", f"Could not open in browser:\n{e}", parent=self.root)

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

        # Clear raw HTML until full body loads
        self._raw_html_content = None

        # Use bodyPreview (already available from list data) as placeholder
        preview_text = msg.get("bodyPreview", "Loading...")
        self.preview_body.config(state=NORMAL)
        self.preview_body.delete("1.0", END)
        self.preview_body.insert("1.0", preview_text)
        self.preview_body.config(state=DISABLED)

        # If in HTML mode, show loading message
        if (self.view_mode.get() or "").strip().lower() == "html" and self._html_frame is not None:
            try:
                loading_html = f"<html><body><p style='color: #888; font-family: Segoe UI;'>Loading email content...</p></body></html>"
                self._html_frame.load_html(loading_html)
            except Exception:
                pass

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
        
        # Store raw HTML for HTML view
        if content_type.lower() == "html":
            self._raw_html_content = raw_content
            plain_content = strip_html(raw_content)
        else:
            self._raw_html_content = None
            plain_content = raw_content

        # Cache the message body for offline access
        if raw_content and not msg.get("_fromCache"):
            try:
                self.cache.save_message_body(msg["id"], content_type, raw_content)
            except Exception:
                pass

        # Update the appropriate view based on current mode
        self.current_message = msg
        
        if (self.view_mode.get() or "").strip().lower() == "html" and self._html_frame is not None:
            # Update HTML view
            self._render_html_preview()
        
        # Always update plain text view (it's the fallback)
        self.preview_body.config(state=NORMAL)
        self.preview_body.delete("1.0", END)
        self.preview_body.insert("1.0", plain_content)
        self.preview_body.config(state=DISABLED)

        # Attachments
        for w in self.att_frame.winfo_children():
            w.destroy()

        msg_id = msg["id"]

        if msg.get("hasAttachments"):
            self.att_frame.pack(fill=X, before=self.email_action_frame)
            Label(self.att_frame, text="ATTACHMENTS", font=("Segoe UI", 8, "bold"),
                  bg=COLOR_BG_LIGHT, fg=COLOR_BORDER).pack(anchor=W, pady=(0, 4))

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
                        self.pdf_viewer.load_pdf_bytes(doc_key, name, content)
                        self.preview_notebook.select(self.pdf_tab)
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
        reply_msg = self.current_message if mode in ("reply", "forward") else None
        ComposeWindow(
            self.root,
            self.graph,
            mode=mode,
            reply_msg=reply_msg,
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
        self.root.destroy()


class SplashScreen:
    """Animated splash: types out 'Geni' letter by letter, then slides 'mail' out from the i."""

    TRANSPARENT_KEY = "#010101"

    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete

        self.win = Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        try:
            self.win.attributes('-transparentcolor', self.TRANSPARENT_KEY)
        except Exception:
            pass

        w, h = 620, 180
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.canvas = Canvas(self.win, width=w, height=h,
                             bg=self.TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack()

        # Fonts
        self._font_geni = tkfont.Font(family="Segoe UI", size=52, weight="bold")
        self._font_mail = tkfont.Font(family="Segoe UI", size=38, weight="bold")

        # Layout: calculate letter positions for "Geni" so they end up
        # left of center, with "mail" filling the right half
        geni_width = self._font_geni.measure("Geni")
        mail_width = self._font_mail.measure("mail")
        total_width = geni_width + mail_width + 4
        self._base_x = (w - total_width) // 2
        self._cy = h // 2

        # Per-letter x positions for "Geni"
        self._letter_x = []
        x = self._base_x
        for ch in "Geni":
            self._letter_x.append(x)
            x += self._font_geni.measure(ch)

        # "mail" slides from the right edge of "i" to its final spot
        i_right_edge = x  # x is already past the last letter after the loop
        self._mail_origin_x = i_right_edge           # start: tucked right behind "i"
        self._mail_final_x = i_right_edge + 4        # end: small gap after "Geni"

        # Baseline-align "mail" (smaller font) with "Geni"
        ascent_geni = self._font_geni.metrics()["ascent"]
        ascent_mail = self._font_mail.metrics()["ascent"]
        self._mail_y_offset = (ascent_geni - ascent_mail) * 0.45

        # Masking: we need to know the "i" region to cover overlap
        self._i_x = self._letter_x[-1]
        self._i_right = i_right_edge

        # 3D color palette (green, beveled)
        self._shadow_deep = "#003300"
        self._shadow_mid = "#005500"
        self._color_main = "#00dd44"
        self._color_shine = "#55ffaa"

        # Animation state
        self._typed = 0
        self._mail_items = []
        self._mail_created = False
        self._i_cover_items = []  # mask + "i" redrawn on top during slide

        self.win.after(300, self._type_next)

    def _draw_3d_text(self, x, y, text, font):
        """Draw text with layered shadow/highlight for a 3D bevel look."""
        # Deep shadow (bottom-right)
        self.canvas.create_text(x + 3, y + 3, text=text, font=font,
                                fill=self._shadow_deep, anchor="w")
        # Mid shadow
        self.canvas.create_text(x + 1, y + 1, text=text, font=font,
                                fill=self._shadow_mid, anchor="w")
        # Main body
        self.canvas.create_text(x, y, text=text, font=font,
                                fill=self._color_main, anchor="w")
        # Top-left highlight (subtle shine)
        self.canvas.create_text(x - 1, y - 1, text=text, font=font,
                                fill=self._color_shine, anchor="w",
)

    def _draw_3d_text_items(self, x, y, text, font):
        """Like _draw_3d_text but returns item IDs for later deletion."""
        items = []
        items.append(self.canvas.create_text(x + 3, y + 3, text=text, font=font,
                                             fill=self._shadow_deep, anchor="w"))
        items.append(self.canvas.create_text(x + 1, y + 1, text=text, font=font,
                                             fill=self._shadow_mid, anchor="w"))
        items.append(self.canvas.create_text(x, y, text=text, font=font,
                                             fill=self._color_main, anchor="w"))
        items.append(self.canvas.create_text(x - 1, y - 1, text=text, font=font,
                                             fill=self._color_shine, anchor="w",
             ))
        return items

    def _type_next(self):
        """Type out G-e-n-i one letter at a time."""
        letters = "Geni"
        if self._typed < len(letters):
            x = self._letter_x[self._typed]
            self._draw_3d_text(x, self._cy, letters[self._typed], self._font_geni)
            self._typed += 1
            self.win.after(150, self._type_next)
        else:
            # Pause briefly, then slide "mail" out
            self.win.after(250, lambda: self._slide_mail(0))

    def _slide_mail(self, frame):
        """Animate 'mail' sliding out from behind the 'i'."""
        total_frames = 14
        frame_delay = 50  # ~700ms total slide

        # Ease-out quadratic (lighter than cubic, no stall at end)
        t = frame / total_frames
        t = t * (2 - t)

        cur_x = self._mail_origin_x + (self._mail_final_x - self._mail_origin_x) * t
        y = self._cy + self._mail_y_offset

        if not self._mail_created:
            # Create mail items once at starting position
            self._mail_items = self._draw_3d_text_items(cur_x, y, "mail", self._font_mail)
            self._mail_created = True
            self._mail_offsets = [(3, 3), (1, 1), (0, 0), (-1, -1)]
        else:
            # Just reposition existing items
            for item, (ox, oy) in zip(self._mail_items, self._mail_offsets):
                self.canvas.coords(item, cur_x + ox, y + oy)

        # Redraw mask + "i" on top so "mail" is hidden behind it
        for item in self._i_cover_items:
            self.canvas.delete(item)
        self._i_cover_items.clear()

        # Mask rectangle over the "i" area in transparent color (hides mail behind it)
        pad = 6
        self._i_cover_items.append(
            self.canvas.create_rectangle(
                self._i_x - pad, self._cy - 50,
                self._i_right, self._cy + 50,
                fill=self.TRANSPARENT_KEY, outline=""))
        # Redraw "i" on top of the mask
        for ox, oy, color in [(3, 3, self._shadow_deep), (1, 1, self._shadow_mid),
                               (0, 0, self._color_main), (-1, -1, self._color_shine)]:
            self._i_cover_items.append(
                self.canvas.create_text(
                    self._i_x + ox, self._cy + oy, text="i",
                    font=self._font_geni, fill=color, anchor="w"))

        if frame < total_frames:
            self.win.after(frame_delay, lambda: self._slide_mail(frame + 1))
        else:
            # Clean up mask on final frame (mail is fully clear of "i" now)
            for item in self._i_cover_items:
                self.canvas.delete(item)
            self._i_cover_items.clear()
            # Redraw clean "i" without mask
            self._draw_3d_text(self._i_x, self._cy, "i", self._font_geni)
            # Hold the final frame, then close
            self.win.after(1100, self._finish)

    def _finish(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.on_complete()


from genimail.ui.splash import SplashScreen


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

