import base64
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from tkinter import (
    BOTH,
    BooleanVar,
    Canvas,
    END,
    FLAT,
    LEFT,
    RIGHT,
    VERTICAL,
    W,
    X,
    Y,
    Button,
    Checkbutton,
    Entry,
    Frame,
    Label,
    Scrollbar,
    StringVar,
    Text,
    Toplevel,
    filedialog,
    messagebox,
)
from tkinter import ttk

from genimail.constants import APP_NAME
from genimail.domain.helpers import build_reply_recipients, format_date, format_size, strip_html
from genimail.domain.quotes import (
    build_quote_context,
    create_quote_doc,
    latest_doc_file,
    open_document_file,
)
from genimail.paths import DEFAULT_QUOTE_TEMPLATE_FILE, QUOTE_DIR
from genimail.ui.theme import T
from genimail.ui.widgets import WarmButton


COLOR_ACCENT = T.ACCENT
COLOR_BG_LIGHT = T.BG_MUTED
COLOR_BG_WHITE = T.BG_SURFACE
COLOR_READ = T.READ
COLOR_TEXT = T.TEXT_PRIMARY
COLOR_BORDER = T.BORDER
FONT_HEADER = T.FONT_HEADER
FONT_NORMAL = T.FONT_LABEL
FONT_SMALL = T.FONT_SMALL
FONT_BODY = T.FONT_BODY


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

        hdr = Frame(main, bg=COLOR_ACCENT, height=50)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(
            hdr,
            text=f"{APP_NAME} - Sign In",
            font=("Segoe UI", 13, "bold"),
            fg="white",
            bg=COLOR_ACCENT,
        ).pack(pady=12)

        body = Frame(main, bg=COLOR_BG_WHITE, padx=25, pady=20)
        body.pack(fill=BOTH, expand=True)

        self.status_label = Label(
            body,
            text="Starting sign-in...",
            font=FONT_NORMAL,
            bg=COLOR_BG_WHITE,
            fg=COLOR_TEXT,
            wraplength=420,
            justify=LEFT,
        )
        self.status_label.pack(anchor=W, pady=(0, 15))

        self.code_var = StringVar(value="...")
        code_frame = Frame(body, bg=COLOR_BG_LIGHT, padx=20, pady=12)
        code_frame.pack(fill=X)
        Label(code_frame, text="Your code:", font=FONT_SMALL, bg=COLOR_BG_LIGHT, fg=COLOR_READ).pack(anchor=W)
        self.code_label = Label(
            code_frame,
            textvariable=self.code_var,
            font=("Consolas", 22, "bold"),
            bg=COLOR_BG_LIGHT,
            fg=COLOR_ACCENT,
        )
        self.code_label.pack(anchor=W, pady=(4, 0))

        hint = Label(
            body,
            text="A browser window has opened. Paste this code there\nand sign in with your Microsoft account.",
            font=FONT_NORMAL,
            bg=COLOR_BG_WHITE,
            fg=COLOR_READ,
            justify=LEFT,
            wraplength=420,
        )
        hint.pack(anchor=W, pady=(15, 0))

        self.waiting_label = Label(
            body,
            text="Waiting for you to sign in...",
            font=("Segoe UI", 9, "italic"),
            bg=COLOR_BG_WHITE,
            fg=COLOR_READ,
        )
        self.waiting_label.pack(anchor=W, pady=(10, 0))

    def show_code(self, flow):
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
        user_email="",
        on_sent=None,
        config=None,
        status_callback=None,
    ):
        self.graph = graph_client
        self.mode = mode
        self.reply_msg = reply_msg
        self.user_email = user_email
        self.on_sent = on_sent
        self.config = config
        self.status_callback = status_callback
        self.attachment_files = []
        self._attachment_keys = set()
        self.last_quote_path = None

        self.win = Toplevel(parent)
        self.win.title(
            f"{'Reply All' if mode == 'reply_all' else 'Reply' if mode == 'reply' else 'Forward' if mode == 'forward' else 'New Email'} - {APP_NAME}"
        )
        self.win.geometry("680x580")
        self.win.minsize(520, 420)
        self.win.configure(bg=T.BG_BASE)

        main = Frame(self.win, bg=T.BG_SURFACE)
        main.pack(fill=BOTH, expand=True, padx=2, pady=2)

        toolbar = Frame(main, bg=T.BG_MUTED, pady=10, padx=12)
        toolbar.pack(fill=X)

        self.send_btn = WarmButton(
            toolbar,
            "Send",
            self._send,
            primary=True,
            width=90,
            height=36,
            bg=T.BG_MUTED,
        )
        self.send_btn.pack(side=LEFT)

        WarmButton(toolbar, "Attach", self._attach, primary=False, width=80, height=36, bg=T.BG_MUTED).pack(
            side=LEFT,
            padx=(10, 0),
        )
        WarmButton(
            toolbar,
            "Quote .doc",
            self._create_quote_doc,
            primary=False,
            width=95,
            height=36,
            bg=T.BG_MUTED,
        ).pack(side=LEFT, padx=(8, 0))
        WarmButton(
            toolbar,
            "Attach Quote",
            self._attach_latest_quote,
            primary=False,
            width=110,
            height=36,
            bg=T.BG_MUTED,
        ).pack(side=LEFT, padx=(8, 0))
        WarmButton(
            toolbar,
            "Template...",
            self._choose_quote_template,
            primary=False,
            width=95,
            height=36,
            bg=T.BG_MUTED,
        ).pack(side=LEFT, padx=(8, 0))

        self.attach_label = Label(toolbar, text="", font=T.FONT_SMALL, bg=T.BG_MUTED, fg=T.TEXT_SECONDARY)
        self.attach_label.pack(side=LEFT, padx=(10, 0))

        fields = Frame(main, bg=T.BG_SURFACE, padx=16, pady=12)
        fields.pack(fill=X)

        row_to = Frame(fields, bg=T.BG_SURFACE)
        row_to.pack(fill=X, pady=4)
        Label(
            row_to,
            text="To:",
            font=T.FONT_LABEL,
            bg=T.BG_SURFACE,
            fg=T.TEXT_SECONDARY,
            width=7,
            anchor="e",
        ).pack(side=LEFT)
        self.to_var = StringVar()
        Entry(
            row_to,
            textvariable=self.to_var,
            font=T.FONT_LABEL,
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            relief=FLAT,
            highlightthickness=1,
            highlightbackground=T.BORDER,
        ).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        row_cc = Frame(fields, bg=T.BG_SURFACE)
        row_cc.pack(fill=X, pady=4)
        Label(
            row_cc,
            text="CC:",
            font=T.FONT_LABEL,
            bg=T.BG_SURFACE,
            fg=T.TEXT_SECONDARY,
            width=7,
            anchor="e",
        ).pack(side=LEFT)
        self.cc_var = StringVar()
        Entry(
            row_cc,
            textvariable=self.cc_var,
            font=T.FONT_LABEL,
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            relief=FLAT,
            highlightthickness=1,
            highlightbackground=T.BORDER,
        ).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        row_subj = Frame(fields, bg=T.BG_SURFACE)
        row_subj.pack(fill=X, pady=4)
        Label(
            row_subj,
            text="Subject:",
            font=T.FONT_LABEL,
            bg=T.BG_SURFACE,
            fg=T.TEXT_SECONDARY,
            width=7,
            anchor="e",
        ).pack(side=LEFT)
        self.subj_var = StringVar()
        Entry(
            row_subj,
            textvariable=self.subj_var,
            font=T.FONT_LABEL,
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            relief=FLAT,
            highlightthickness=1,
            highlightbackground=T.BORDER,
        ).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), ipady=4)

        Frame(main, bg=T.BORDER, height=1).pack(fill=X)

        body_frame = Frame(main, bg=T.BG_SURFACE)
        body_frame.pack(fill=BOTH, expand=True)
        self.body_text = Text(
            body_frame,
            font=T.FONT_BODY,
            wrap="word",
            relief=FLAT,
            bg=T.BG_SURFACE,
            fg=T.TEXT_PRIMARY,
            padx=16,
            pady=12,
            insertbackground=T.TEXT_PRIMARY,
        )
        self.body_text.pack(fill=BOTH, expand=True)

        if mode in ("reply", "reply_all", "forward") and reply_msg:
            sender = reply_msg.get("from", {}).get("emailAddress", {})
            to_email = sender.get("address", "")

            if mode == "reply":
                to_list, cc_list = build_reply_recipients(
                    reply_msg,
                    current_user_email=self.user_email,
                    include_all=False,
                )
                self.to_var.set("; ".join(to_list))
                self.cc_var.set("")
            elif mode == "reply_all":
                to_list, cc_list = build_reply_recipients(
                    reply_msg,
                    current_user_email=self.user_email,
                    include_all=True,
                )
                self.to_var.set("; ".join(to_list))
                self.cc_var.set("; ".join(cc_list))
            else:
                self.to_var.set("")
                self.cc_var.set("")

            subj = reply_msg.get("subject", "")
            if mode in ("reply", "reply_all") and not subj.lower().startswith("re:"):
                subj = f"Re: {subj}"
            elif mode == "forward" and not subj.lower().startswith("fw:"):
                subj = f"Fw: {subj}"
            self.subj_var.set(subj)

            body_content = reply_msg.get("body", {}).get("content", "")
            if reply_msg.get("body", {}).get("contentType", "").lower() == "html":
                body_content = strip_html(body_content)

            orig_from = sender.get("name", to_email)
            orig_date = format_date(reply_msg.get("receivedDateTime", ""))
            orig_subj = reply_msg.get("subject", "")
            quote = f"\n\n--- Original Message ---\nFrom: {orig_from}\nDate: {orig_date}\nSubject: {orig_subj}\n\n{body_content}"
            if mode == "forward":
                self.body_text.insert("1.0", quote)
            else:
                self.body_text.insert("1.0", "\n" + quote)

    def _status(self, text):
        if self.status_callback:
            try:
                self.status_callback(text)
            except Exception:
                pass

    def _refresh_attachment_label(self):
        count = len(self.attachment_files)
        if count:
            self.attach_label.config(text=f"{count} attachment(s)")
        else:
            self.attach_label.config(text="")

    def _add_attachment_path(self, path):
        abs_path = os.path.abspath(path)
        key = abs_path.lower()
        if key in self._attachment_keys:
            return False
        self._attachment_keys.add(key)
        self.attachment_files.append(abs_path)
        return True

    def _attach_files(self, paths):
        added = 0
        for path in paths:
            if self._add_attachment_path(path):
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
        to_list = [a.strip() for a in to_str.replace(";", ",").split(",") if a.strip()]
        if not to_list:
            messagebox.showwarning("Missing Recipient", "Please enter at least one recipient.", parent=self.win)
            return
        cc_str = self.cc_var.get().strip()
        cc_list = [a.strip() for a in cc_str.replace(";", ",").split(",") if a.strip()] if cc_str else []
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

        self.send_btn.set_disabled(True)
        self._status("Sending...")

        attachments = []
        for path in self.attachment_files:
            try:
                with open(path, "rb") as f:
                    content = base64.b64encode(f.read()).decode("ascii")
                attachments.append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(path),
                        "contentBytes": content,
                    }
                )
            except Exception as e:
                self._on_send_fail(f"Attachment error ({os.path.basename(path)}): {e}")
                return

        def do_send():
            try:
                self.graph.send_mail(
                    to_list,
                    cc_list,
                    subject,
                    body,
                    attachments=attachments or None,
                    reply_to_id=(self.reply_msg.get("id") if self.mode in ("reply", "reply_all") and self.reply_msg else None),
                    reply_mode=self.mode,
                )
                self.win.after(0, self._on_send_success)
            except Exception as e:
                self.win.after(0, lambda: self._on_send_fail(str(e)))

        threading.Thread(target=do_send, daemon=True).start()

    def _on_send_fail(self, message):
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

        hdr = Frame(main, bg=COLOR_BG_LIGHT, padx=10, pady=6)
        hdr.pack(fill=X)
        Label(hdr, text="All Attachments", font=FONT_HEADER, bg=COLOR_BG_LIGHT).pack(side=LEFT)

        self.status_lbl = Label(hdr, text="Loading...", font=FONT_SMALL, bg=COLOR_BG_LIGHT, fg=COLOR_READ)
        self.status_lbl.pack(side=RIGHT)

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

        btn_frame = Frame(main, bg=COLOR_BG_WHITE, padx=10, pady=8)
        btn_frame.pack(fill=X)
        Button(
            btn_frame,
            text="Download Selected",
            font=FONT_NORMAL,
            bg=COLOR_ACCENT,
            fg="white",
            relief=FLAT,
            command=self._download_selected,
        ).pack(side=RIGHT)

        self.att_data = []
        self._item_to_att = {}

        self.messages_with_att = [m for m in all_messages if m.get("hasAttachments")]
        threading.Thread(target=self._load_attachments, daemon=True).start()

    def _load_attachments(self):
        count = 0
        lock = threading.Lock()

        def fetch_one(msg):
            nonlocal count
            msg_id = msg["id"]
            try:
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
        self.win.after(0, lambda: self.status_lbl.config(text=f"{final_count} attachment(s) found"))

    def _insert_att_row(self, info):
        item_id = self.tree.insert(
            "",
            END,
            values=(info["name"], info["from"], info["date"], format_size(info["size"])),
        )
        self._item_to_att[item_id] = info

    def _download_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select an attachment to download.", parent=self.win)
            return
        item = sel[0]
        try:
            info = self._item_to_att[item]
        except (KeyError, AttributeError):
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Attachment",
            initialfile=info["name"],
            parent=self.win,
        )
        if not save_path:
            return

        def do_download():
            try:
                att = self.graph.download_attachment(info["msg_id"], info["att_id"])
                content = base64.b64decode(att.get("contentBytes", ""))
                with open(save_path, "wb") as f:
                    f.write(content)
                self.win.after(
                    0,
                    lambda: messagebox.showinfo("Saved", f"Attachment saved to:\n{save_path}", parent=self.win),
                )
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror("Download Error", str(e), parent=self.win))

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

        hdr = Frame(main, bg=COLOR_BG_LIGHT, padx=10, pady=8)
        hdr.pack(fill=X)
        Label(hdr, text="Company Manager", font=FONT_HEADER, bg=COLOR_BG_LIGHT).pack(side=LEFT)
        Label(
            hdr,
            text="Double-click a domain to assign a label",
            font=FONT_SMALL,
            bg=COLOR_BG_LIGHT,
            fg=COLOR_READ,
        ).pack(side=RIGHT)

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

        btn_frame = Frame(main, bg=COLOR_BG_WHITE, padx=10, pady=8)
        btn_frame.pack(fill=X)

        Button(
            btn_frame,
            text="Edit Label",
            font=FONT_NORMAL,
            bg=COLOR_ACCENT,
            fg="white",
            relief=FLAT,
            command=self._edit_selected,
        ).pack(side=LEFT)
        Button(
            btn_frame,
            text="Auto-Label Common",
            font=FONT_NORMAL,
            relief=FLAT,
            command=self._auto_label,
        ).pack(side=LEFT, padx=(8, 0))
        Button(btn_frame, text="Refresh", font=FONT_NORMAL, relief=FLAT, command=self._load_data).pack(side=RIGHT)

        self._load_data()

    def _load_data(self):
        self.tree.delete(*self.tree.get_children())
        try:
            domains = self.cache.get_all_domains()
            for domain_data in domains:
                label = domain_data.get("company_label") or ""
                last = format_date(domain_data.get("last_email") or "")
                self.tree.insert(
                    "",
                    END,
                    values=(domain_data["domain"], label, domain_data["count"], last),
                    tags=("labeled" if label else "unlabeled",),
                )
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

        edit_win = Toplevel(self.win)
        edit_win.title(f"Label: {domain}")
        edit_win.geometry("350x130")
        edit_win.transient(self.win)
        edit_win.grab_set()

        f = Frame(edit_win, bg=COLOR_BG_WHITE, padx=15, pady=15)
        f.pack(fill=BOTH, expand=True)

        Label(f, text=f"Set company label for @{domain}:", font=FONT_NORMAL, bg=COLOR_BG_WHITE).pack(anchor=W)

        label_var = StringVar(value=current_label)
        entry = Entry(f, textvariable=label_var, font=FONT_NORMAL)
        entry.pack(fill=X, pady=(4, 12))
        entry.focus_set()
        entry.select_range(0, END)

        def save():
            new_label = label_var.get().strip()
            self.cache.label_domain(domain, new_label if new_label else None)
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
        Button(f, text="Save", font=FONT_NORMAL, bg=COLOR_ACCENT, fg="white", relief=FLAT, command=save).pack(
            side=RIGHT
        )

    def _auto_label(self):
        known_domains = {
            "amazon.com": "Amazon",
            "amazon.ca": "Amazon",
            "google.com": "Google",
            "gmail.com": "Gmail",
            "microsoft.com": "Microsoft",
            "outlook.com": "Outlook",
            "apple.com": "Apple",
            "icloud.com": "iCloud",
            "paypal.com": "PayPal",
            "paypal.ca": "PayPal",
            "facebook.com": "Facebook",
            "meta.com": "Meta",
            "twitter.com": "Twitter",
            "x.com": "X",
            "linkedin.com": "LinkedIn",
            "netflix.com": "Netflix",
            "spotify.com": "Spotify",
            "uber.com": "Uber",
            "ubereats.com": "Uber Eats",
            "doordash.com": "DoorDash",
            "shopify.com": "Shopify",
            "stripe.com": "Stripe",
            "github.com": "GitHub",
            "docusign.com": "DocuSign",
            "docusign.net": "DocuSign",
            "interac.ca": "Interac",
        }

        labeled_count = 0
        companies = self.config.get("companies", {})

        for domain, label in known_domains.items():
            count = self.cache.label_domain(domain, label)
            if count > 0:
                labeled_count += count
                companies[domain] = label

        self.config.set("companies", companies)
        self._load_data()
        if self.on_update:
            self.on_update()

        messagebox.showinfo(
            "Auto-Label Complete",
            f"Labeled {labeled_count} emails from known companies.",
            parent=self.win,
        )


class CloudPdfLinkDialog:
    """Select cloud-hosted PDF links to fetch/open."""

    def __init__(self, parent, links):
        self.links = list(links or [])
        self.result = []
        self.vars = []

        self.win = Toplevel(parent)
        self.win.title("Linked Cloud PDFs")
        self.win.geometry("760x420")
        self.win.minsize(620, 320)
        self.win.transient(parent)
        self.win.grab_set()

        main = Frame(self.win, bg=COLOR_BG_WHITE)
        main.pack(fill=BOTH, expand=True)

        header = Frame(main, bg=COLOR_BG_LIGHT, padx=12, pady=10)
        header.pack(fill=X)
        Label(header, text="Linked Cloud PDFs", font=FONT_HEADER, bg=COLOR_BG_LIGHT, fg=COLOR_TEXT).pack(
            side=LEFT
        )
        Label(
            header,
            text="Select links to download and open in PDF tabs",
            font=FONT_SMALL,
            bg=COLOR_BG_LIGHT,
            fg=COLOR_READ,
        ).pack(side=RIGHT)

        body = Frame(main, bg=COLOR_BG_WHITE)
        body.pack(fill=BOTH, expand=True, padx=10, pady=10)

        canvas = Canvas(body, bg=COLOR_BG_WHITE, highlightthickness=0)
        scroll = Scrollbar(body, orient=VERTICAL, command=canvas.yview)
        inner = Frame(canvas, bg=COLOR_BG_WHITE)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        if not self.links:
            Label(inner, text="No cloud links found in this message.", font=FONT_NORMAL, bg=COLOR_BG_WHITE).pack(
                anchor="w", padx=8, pady=8
            )
        else:
            for link in self.links:
                row = Frame(inner, bg=COLOR_BG_WHITE, pady=5)
                row.pack(fill=X)
                var = BooleanVar(value=True)
                self.vars.append(var)
                Checkbutton(
                    row,
                    variable=var,
                    bg=COLOR_BG_WHITE,
                    activebackground=COLOR_BG_WHITE,
                ).pack(side=LEFT, padx=(4, 8))
                text = f"{link.get('source', 'External')}: {link.get('suggested_name', 'linked.pdf')}"
                Label(row, text=text, font=FONT_NORMAL, bg=COLOR_BG_WHITE, fg=COLOR_TEXT).pack(side=LEFT, anchor="w")
                Label(
                    row,
                    text=link.get("original_url", ""),
                    font=FONT_SMALL,
                    bg=COLOR_BG_WHITE,
                    fg=COLOR_READ,
                    wraplength=560,
                    justify=LEFT,
                ).pack(side=LEFT, anchor="w", padx=(10, 0))

        footer = Frame(main, bg=COLOR_BG_WHITE, padx=12, pady=10)
        footer.pack(fill=X)
        WarmButton(footer, "Select All", self._select_all, primary=False, width=90, height=30, bg=COLOR_BG_WHITE).pack(
            side=LEFT
        )
        WarmButton(footer, "Clear", self._clear_all, primary=False, width=70, height=30, bg=COLOR_BG_WHITE).pack(
            side=LEFT, padx=(8, 0)
        )
        WarmButton(
            footer, "Cancel", self._cancel, primary=False, width=80, height=30, bg=COLOR_BG_WHITE
        ).pack(side=RIGHT)
        WarmButton(
            footer,
            "Open Selected",
            self._accept,
            primary=True,
            width=120,
            height=30,
            bg=COLOR_BG_WHITE,
        ).pack(side=RIGHT, padx=(0, 8))

    def _select_all(self):
        for var in self.vars:
            var.set(True)

    def _clear_all(self):
        for var in self.vars:
            var.set(False)

    def _cancel(self):
        self.result = []
        self.win.destroy()

    def _accept(self):
        self.result = [link for var, link in zip(self.vars, self.links) if var.get()]
        self.win.destroy()

    def show(self):
        self.win.wait_window()
        return self.result
