from tkinter import END, Canvas, Entry, FLAT, Frame, X

from genimail.ui.theme import T


class WarmButton(Canvas):
    """Soft rounded button with subtle shadow."""

    def __init__(self, parent, text, command, primary=True, width=120, height=36, **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height + 3,
            bg=kwargs.get("bg", T.BG_MUTED),
            highlightthickness=0,
        )
        self.text = text
        self.command = command
        self.primary = primary
        self.w, self.h = width, height
        self._hovered = False
        self._disabled = False

        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._on_click)
        self.configure(cursor="hand2")

        self._draw()

    def _set_hover(self, hovered):
        if not self._disabled:
            self._hovered = hovered
            self._draw()

    def _draw(self):
        self.delete("all")

        r = 8
        x1, y1 = 2, 1
        x2, y2 = self.w - 2, self.h - 1

        if not self._disabled:
            self._rounded_rect(x1 + 1, y1 + 2, x2 + 1, y2 + 2, r, T.SHADOW, "")

        if self._disabled:
            fill = T.BG_MUTED
            outline = T.BORDER
            text_color = T.TEXT_MUTED
        elif self.primary:
            fill = T.ACCENT_HOVER if self._hovered else T.ACCENT
            outline = fill
            text_color = T.ACCENT_TEXT
        else:
            fill = T.BG_HOVER if self._hovered else T.BG_SURFACE
            outline = T.ACCENT if self._hovered else T.BORDER
            text_color = T.ACCENT if self._hovered else T.TEXT_PRIMARY

        self._rounded_rect(x1, y1, x2, y2, r, fill, outline)
        self.create_text(self.w // 2, self.h // 2, text=self.text, font=T.FONT_BUTTON, fill=text_color)

    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(points, fill=fill, outline=outline, width=1, smooth=True)

    def _on_click(self, e):
        if not self._disabled and self.command:
            self.command()

    def set_disabled(self, disabled):
        self._disabled = disabled
        self.configure(cursor="" if disabled else "hand2")
        self._draw()


class PillToggle(Canvas):
    """Segmented pill toggle for options."""

    def __init__(self, parent, variable, options, width=180, height=30, **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=kwargs.get("bg", T.BG_SURFACE),
            highlightthickness=0,
        )
        self.variable = variable
        self.options = options
        self.w = width
        self.h = height
        self.segment_w = width // len(options)

        self.bind("<Button-1>", self._on_click)
        self.variable.trace_add("write", lambda *args: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        self._rounded_rect(0, 0, self.w, self.h, 6, T.BG_MUTED, "")

        current = self.variable.get()
        for i, opt in enumerate(self.options):
            x1 = i * self.segment_w
            x2 = x1 + self.segment_w
            if opt == current:
                self._rounded_rect(x1 + 2, 2, x2 - 2, self.h - 2, 5, T.BG_SURFACE, T.BORDER)
                color = T.TEXT_PRIMARY
            else:
                color = T.TEXT_MUTED
            self.create_text((x1 + x2) // 2, self.h // 2, text=opt, font=T.FONT_SMALL, fill=color)

    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(points, fill=fill, outline=outline if outline else "", smooth=True)

    def _on_click(self, e):
        idx = min(e.x // self.segment_w, len(self.options) - 1)
        self.variable.set(self.options[idx])


class StyledEntry(Frame):
    """Rounded entry field with warm styling."""

    def __init__(self, parent, textvariable=None, placeholder="", **kwargs):
        bg = kwargs.pop("bg", T.BG_MUTED)
        super().__init__(parent, bg=bg)

        self.placeholder = placeholder
        self.showing_placeholder = True

        self.inner = Frame(self, bg=T.BG_INPUT, highlightbackground=T.BORDER, highlightthickness=1)
        self.inner.pack(fill=X, padx=1, pady=1)

        self.entry = Entry(
            self.inner,
            textvariable=textvariable,
            font=T.FONT_LABEL,
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            relief=FLAT,
            insertbackground=T.TEXT_PRIMARY,
        )
        self.entry.pack(fill=X, padx=8, pady=6)

        if placeholder:
            self.entry.insert(0, placeholder)
            self.entry.config(fg=T.TEXT_MUTED)
            self.entry.bind("<FocusIn>", self._on_focus_in)
            self.entry.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, e):
        if self.showing_placeholder:
            self.entry.delete(0, END)
            self.entry.config(fg=T.TEXT_PRIMARY)
            self.showing_placeholder = False

    def _on_focus_out(self, e):
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=T.TEXT_MUTED)
            self.showing_placeholder = True

    def get(self):
        if self.showing_placeholder:
            return ""
        return self.entry.get()

    def bind(self, event, handler):
        self.entry.bind(event, handler)

