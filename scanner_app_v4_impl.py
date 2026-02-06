"""
GENIS SCANNER v4 — "Paper Studio" Direction

DESIGN PHILOSOPHY: The Anti-Tech Scanner
Instead of dark/cyber, this is warm, tactile, and paper-inspired.
Feels like a creative studio, not a control room.

CONCEPT:
┌─────────────────────────────────────────────────────────────────────────────┐
│ What if a scanner app felt like handling actual paper?                      │
│ Light, airy, warm. Documents as the hero. Tools fade into the background.  │
└─────────────────────────────────────────────────────────────────────────────┘

CRITICAL DECISIONS — Different from v3:
┌─────────────────────────────────────────────────────────────────────────────┐
│ LIGHT MODE: Cream/warm white base. Easier on eyes for document work.       │
│ Scanners often live in bright offices, not dark rooms.                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ WARM ACCENT: Terracotta/coral (#E07A5F) instead of cyan.                   │
│ Feels approachable, not clinical. Invites interaction.                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ DOCUMENT-FIRST: Preview shows page with subtle paper shadow.               │
│ Thumbnails styled as stacked paper, not tech cards.                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CENTERED LAYOUT: Symmetrical, calm. Not a cramped control panel.           │
│ Generous whitespace. Let the scanned content breathe.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ TOOLBAR TOP: Traditional placement. Familiar = faster learning.            │
│ v3 was innovative; v4 prioritizes immediate usability.                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOFT SHADOWS: Depth through shadows, not borders.                          │
│ Elements float on the page like actual paper.                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ROUNDED EVERYTHING: Soft corners everywhere. Friendly, not sharp.          │
│ 12px radius minimum. Feels touchable.                                      │
└─────────────────────────────────────────────────────────────────────────────┘

TYPOGRAPHY: Serif for display, sans for UI
- Headers use Georgia/serif for warmth and document feel
- UI elements use system sans-serif for clarity
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import io
import os
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCANS_DIR = os.path.join(APP_DIR, "scans")
PDF_DIR = os.path.join(APP_DIR, "pdf")
SCAN_DPI = 600

# WIA Constants
WIA_DEVICE_TYPE_SCANNER = 1
WIA_IMG_FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
WIA_IPS_CUR_INTENT = 6146
WIA_IPS_XRES = 6147
WIA_IPS_YRES = 6148
WIA_IPS_BRIGHTNESS = 6154
WIA_IPS_CONTRAST = 6155
WIA_INTENT_IMAGE_TYPE_COLOR = 1
WIA_INTENT_IMAGE_TYPE_GRAYSCALE = 2
WIA_INTENT_IMAGE_TYPE_TEXT = 4


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS — Warm Paper Studio
# ═══════════════════════════════════════════════════════════════════════════════

class T:
    """Light, warm, paper-inspired palette."""
    
    # ── Backgrounds ────────────────────────────────────────────────────────────
    BG_BASE = "#FAF8F5"        # Warm off-white (like quality paper)
    BG_SURFACE = "#FFFFFF"     # Pure white cards
    BG_MUTED = "#F0EDE8"       # Subtle differentiation
    BG_HOVER = "#F5F2ED"       # Hover state
    
    # ── Primary Accent: Terracotta ─────────────────────────────────────────────
    ACCENT = "#E07A5F"         # Warm terracotta
    ACCENT_HOVER = "#C96A52"   # Darker on hover
    ACCENT_LIGHT = "#F4D1C7"   # Light tint for backgrounds
    ACCENT_TEXT = "#FFFFFF"    # Text on accent
    
    # ── Secondary: Sage Green ──────────────────────────────────────────────────
    SECONDARY = "#81B29A"      # Calm sage green
    SECONDARY_HOVER = "#6A9C83"
    
    # ── Text ───────────────────────────────────────────────────────────────────
    TEXT_PRIMARY = "#3D405B"   # Deep blue-gray (not pure black)
    TEXT_SECONDARY = "#6B6E8A" # Lighter variant
    TEXT_MUTED = "#A0A3B5"     # Hints, placeholders
    
    # ── Semantic ───────────────────────────────────────────────────────────────
    DANGER = "#E07A5F"         # Same as accent (warm palette)
    SUCCESS = "#81B29A"        # Sage green
    BORDER = "#E8E4DE"         # Subtle warm gray
    SHADOW = "#D5D2CC"         # Light shadow (tkinter doesn't support alpha)
    
    # ── Typography ─────────────────────────────────────────────────────────────
    FONT_DISPLAY = ("Georgia", 18)
    FONT_HEADING = ("Georgia", 13)
    FONT_BODY = ("Segoe UI", 10)
    FONT_LABEL = ("Segoe UI", 9)
    FONT_SMALL = ("Segoe UI", 8)
    FONT_BUTTON = ("Segoe UI Semibold", 10)
    
    # ── Spacing ────────────────────────────────────────────────────────────────
    S1 = 4
    S2 = 8
    S3 = 16
    S4 = 24
    S5 = 32
    S6 = 48
    
    # ── Geometry ───────────────────────────────────────────────────────────────
    RADIUS = 12                # Generous rounding
    THUMB_SIZE = 90
    TOOLBAR_H = 64
    SIDEBAR_W = 200


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM COMPONENTS — Soft & Tactile
# ═══════════════════════════════════════════════════════════════════════════════

class WarmButton(tk.Canvas):
    """
    Soft, rounded button with subtle shadow.
    Primary = filled terracotta. Secondary = outlined.
    """
    
    def __init__(self, parent, text, command, primary=True, width=140, height=44):
        super().__init__(parent, width=width, height=height + 4,  # +4 for shadow
                        bg=T.BG_BASE, highlightthickness=0)
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
        
        r = T.RADIUS
        x1, y1 = 2, 2
        x2, y2 = self.w - 2, self.h
        
        # Shadow (offset down)
        if not self._disabled:
            self._rounded_rect(x1 + 1, y1 + 3, x2 + 1, y2 + 3, r, T.SHADOW, "")
        
        # Button body
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
        
        # Text
        self.create_text(
            self.w // 2, (self.h // 2) + 1,
            text=self.text, font=T.FONT_BUTTON, fill=text_color
        )
    
    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        """Draw a proper rounded rectangle."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        self.create_polygon(points, fill=fill, outline=outline, width=2, smooth=True)
    
    def _on_click(self, e):
        if not self._disabled and self.command:
            self.command()
    
    def set_disabled(self, disabled):
        self._disabled = disabled
        self.configure(cursor="" if disabled else "hand2")
        self._draw()


class PaperCard(tk.Frame):
    """
    A floating card with subtle shadow, like paper on a desk.
    """
    
    def __init__(self, parent, **kwargs):
        # Outer frame for shadow effect
        super().__init__(parent, bg=T.BG_BASE, **kwargs)
        
        # Inner white card
        self.inner = tk.Frame(self, bg=T.BG_SURFACE)
        self.inner.pack(fill="both", expand=True, padx=2, pady=(1, 4))
        
        # We fake the shadow with the outer bg showing through padding


class SoftSlider(tk.Canvas):
    """Rounded, friendly slider."""
    
    def __init__(self, parent, variable, from_=-100, to=100, width=180):
        super().__init__(parent, width=width, height=36,
                        bg=T.BG_SURFACE, highlightthickness=0)
        self.variable = variable
        self.from_ = from_
        self.to = to
        self.w = width
        self._dragging = False
        
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, '_dragging', False))
        
        self._draw()
    
    def _val_to_x(self, val):
        pad = 18
        ratio = (val - self.from_) / (self.to - self.from_)
        return pad + ratio * (self.w - 2 * pad)
    
    def _x_to_val(self, x):
        pad = 18
        ratio = max(0, min(1, (x - pad) / (self.w - 2 * pad)))
        return int(self.from_ + ratio * (self.to - self.from_))
    
    def _draw(self):
        self.delete("all")
        val = self.variable.get()
        thumb_x = self._val_to_x(val)
        y = 18
        pad = 18
        
        # Track (pill shape)
        self.create_line(pad, y, self.w - pad, y, fill=T.BG_MUTED, width=8, capstyle="round")
        
        # Filled portion
        center = self._val_to_x(0)
        if val >= 0:
            self.create_line(center, y, thumb_x, y, fill=T.ACCENT, width=8, capstyle="round")
        else:
            self.create_line(thumb_x, y, center, y, fill=T.ACCENT, width=8, capstyle="round")
        
        # Thumb (circle with border)
        self.create_oval(
            thumb_x - 10, y - 10, thumb_x + 10, y + 10,
            fill=T.BG_SURFACE, outline=T.ACCENT, width=3
        )
        
        # Value
        self.create_text(
            self.w - 2, y, text=str(val), anchor="e",
            font=T.FONT_SMALL, fill=T.TEXT_SECONDARY
        )
    
    def _on_click(self, e):
        self._dragging = True
        self._update(e.x)
    
    def _on_drag(self, e):
        if self._dragging:
            self._update(e.x)
    
    def _update(self, x):
        self.variable.set(self._x_to_val(x))
        self._draw()


class PillToggle(tk.Canvas):
    """Segmented pill toggle for options like color mode."""
    
    def __init__(self, parent, variable, options, width=200):
        height = 36
        super().__init__(parent, width=width, height=height,
                        bg=T.BG_SURFACE, highlightthickness=0)
        self.variable = variable
        self.options = options
        self.w = width
        self.h = height
        self.segment_w = width // len(options)
        
        self.bind("<Button-1>", self._on_click)
        self._draw()
    
    def _draw(self):
        self.delete("all")
        
        # Background pill
        self._rounded_rect(0, 0, self.w, self.h, 8, T.BG_MUTED, "")
        
        # Segments
        current = self.variable.get()
        for i, opt in enumerate(self.options):
            x1 = i * self.segment_w
            x2 = x1 + self.segment_w
            
            if opt == current:
                # Selected segment
                self._rounded_rect(x1 + 2, 2, x2 - 2, self.h - 2, 6, T.BG_SURFACE, T.BORDER)
                color = T.TEXT_PRIMARY
            else:
                color = T.TEXT_MUTED
            
            self.create_text(
                (x1 + x2) // 2, self.h // 2,
                text=opt, font=T.FONT_SMALL, fill=color
            )
    
    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(points, fill=fill, outline=outline, smooth=True)
    
    def _on_click(self, e):
        idx = min(e.x // self.segment_w, len(self.options) - 1)
        self.variable.set(self.options[idx])
        self._draw()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class ScannedPage:
    def __init__(self, image: Image.Image, index: int):
        self.image = image
        self.index = index
        self.thumbnail = self._make_thumbnail()

    def _make_thumbnail(self):
        thumb = self.image.copy()
        thumb.thumbnail((T.THUMB_SIZE, T.THUMB_SIZE * 1.4), Image.Resampling.LANCZOS)
        return thumb

    def rotate(self, degrees=-90):
        self.image = self.image.rotate(degrees, expand=True)
        self.thumbnail = self._make_thumbnail()


# ═══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL — Paper Stack Style
# ═══════════════════════════════════════════════════════════════════════════════

class PaperThumbnail(tk.Canvas):
    """
    Thumbnail styled as a piece of paper with subtle shadow.
    Selected state shows terracotta border.
    """
    
    def __init__(self, parent, page, index, is_selected, on_select, on_rotate):
        self.page = page
        self.index = index
        self.is_selected = is_selected
        self.on_select = on_select
        self.on_rotate = on_rotate
        
        # Size with room for shadow
        self.pw = page.thumbnail.width + 12
        self.ph = page.thumbnail.height + 24
        
        super().__init__(parent, width=self.pw, height=self.ph,
                        bg=T.BG_MUTED, highlightthickness=0)
        
        self._tk_img = ImageTk.PhotoImage(page.thumbnail)
        self._hovered = False
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", lambda e: on_select(index))
        self.bind("<Double-Button-1>", lambda e: on_rotate(index))
        self.configure(cursor="hand2")
        
        self._draw()
    
    def _on_enter(self, e):
        self._hovered = True
        self._draw()
    
    def _on_leave(self, e):
        self._hovered = False
        self._draw()
    
    def _draw(self):
        self.delete("all")
        
        img_w = self.page.thumbnail.width
        img_h = self.page.thumbnail.height
        
        x = (self.pw - img_w) // 2
        y = 4
        
        # Shadow
        self.create_rectangle(x + 3, y + 4, x + img_w + 3, y + img_h + 4,
                             fill=T.SHADOW, outline="")
        
        # Paper background
        border = T.ACCENT if self.is_selected else (T.BORDER if not self._hovered else T.TEXT_MUTED)
        self.create_rectangle(x, y, x + img_w, y + img_h,
                             fill=T.BG_SURFACE, outline=border, width=2 if self.is_selected else 1)
        
        # Image
        self.create_image(x, y, image=self._tk_img, anchor="nw")
        
        # Page number
        self.create_text(
            self.pw // 2, self.ph - 8,
            text=f"{self.index + 1}",
            font=T.FONT_SMALL,
            fill=T.ACCENT if self.is_selected else T.TEXT_SECONDARY
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ScannerAppV4:
    def __init__(self, root: tk.Tk):
        self.root = root
        if hasattr(self.root, "title"):
            self.root.title("Genis Paper Studio")
        if hasattr(self.root, "geometry"):
            self.root.geometry("950x680")
        if hasattr(self.root, "minsize"):
            self.root.minsize(800, 600)
        self.root.configure(bg=T.BG_BASE)
        
        self.pages: list[ScannedPage] = []
        self.selected_index: int = -1
        self.scanning = False
        self.page_counter = 0
        
        os.makedirs(SCANS_DIR, exist_ok=True)
        os.makedirs(PDF_DIR, exist_ok=True)
        
        self._preview_image = None
        self._thumb_refs = []
        
        self._build_ui()
    
    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT — Centered, Calm, Symmetrical
    # ══════════════════════════════════════════════════════════════════════════
    
    def _build_ui(self):
        """
        Layout:
        ┌────────────────────────────────────────────────────────────────┐
        │  TOOLBAR: [Scan] [Save▾]                     [Settings ▾]     │
        ├────────────────────────────────────────────────────────────────┤
        │                                                                │
        │                    ┌──────────────────┐                        │
        │                    │                  │                        │
        │                    │   PREVIEW        │                        │
        │                    │   (document)     │                        │
        │                    │                  │                        │
        │                    └──────────────────┘                        │
        │                                                                │
        ├────────────────────────────────────────────────────────────────┤
        │  [1] [2] [3] [4] ... (paper thumbnails)                        │
        └────────────────────────────────────────────────────────────────┘
        """
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        
        self._build_toolbar()
        self._build_preview()
        self._build_page_strip()
        self._build_settings_popup()
    
    def _build_toolbar(self):
        """Top toolbar with primary actions."""
        toolbar = tk.Frame(self.root, bg=T.BG_SURFACE, height=T.TOOLBAR_H)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        
        # Left side: Logo + Scan
        left = tk.Frame(toolbar, bg=T.BG_SURFACE)
        left.pack(side="left", fill="y", padx=T.S4)
        
        # Logo
        tk.Label(
            left, text="Paper Studio",
            font=T.FONT_DISPLAY, bg=T.BG_SURFACE, fg=T.TEXT_PRIMARY
        ).pack(side="left", pady=T.S3)
        
        # Scan button
        self.scan_btn = WarmButton(
            left, "⊕ Scan Page", self._on_scan_page,
            primary=True, width=130, height=40
        )
        self.scan_btn.pack(side="left", padx=(T.S4, 0), pady=T.S2)
        
        # Right side: Save + Settings
        right = tk.Frame(toolbar, bg=T.BG_SURFACE)
        right.pack(side="right", fill="y", padx=T.S4)
        
        # Settings toggle
        self.settings_btn = WarmButton(
            right, "⚙", self._toggle_settings,
            primary=False, width=44, height=40
        )
        self.settings_btn.pack(side="right", pady=T.S2)
        
        # Save button
        self.save_btn = WarmButton(
            right, "Save As...", self._on_save,
            primary=False, width=100, height=40
        )
        self.save_btn.pack(side="right", padx=(0, T.S2), pady=T.S2)
        
        # Format selector
        self.format_var = tk.StringVar(value="PDF")
        format_toggle = PillToggle(right, self.format_var, ["PDF", "PNG", "JPG"], width=150)
        format_toggle.pack(side="right", padx=(0, T.S3), pady=T.S2)
    
    def _build_preview(self):
        """Central preview area with document display."""
        self.preview_container = tk.Frame(self.root, bg=T.BG_BASE)
        self.preview_container.grid(row=1, column=0, sticky="nsew", padx=T.S5, pady=T.S4)
        self.preview_container.columnconfigure(0, weight=1)
        self.preview_container.rowconfigure(0, weight=1)
        
        # Preview label (centered)
        self.preview_label = tk.Label(
            self.preview_container, bg=T.BG_BASE,
            text="Scan your first page to begin",
            font=T.FONT_HEADING, fg=T.TEXT_MUTED
        )
        self.preview_label.grid(row=0, column=0)
        self.preview_label.bind("<Configure>", lambda e: self._update_preview())
    
    def _build_page_strip(self):
        """Bottom horizontal strip of paper thumbnails."""
        strip_outer = tk.Frame(self.root, bg=T.BG_MUTED, height=160)
        strip_outer.grid(row=2, column=0, sticky="ew")
        strip_outer.grid_propagate(False)
        
        # Scrollable canvas
        self.strip_canvas = tk.Canvas(
            strip_outer, bg=T.BG_MUTED, height=150, highlightthickness=0
        )
        self.strip_canvas.pack(fill="both", expand=True, padx=T.S4, pady=T.S2)
        
        self.strip_inner = tk.Frame(self.strip_canvas, bg=T.BG_MUTED)
        self.strip_canvas.create_window((0, 0), window=self.strip_inner, anchor="nw")
        
        self.strip_inner.bind("<Configure>",
            lambda e: self.strip_canvas.configure(scrollregion=self.strip_canvas.bbox("all")))
        
        self.strip_canvas.bind("<MouseWheel>",
            lambda e: self.strip_canvas.xview_scroll(int(-e.delta / 120), "units"))
        self.strip_inner.bind("<MouseWheel>",
            lambda e: self.strip_canvas.xview_scroll(int(-e.delta / 120), "units"))
    
    def _build_settings_popup(self):
        """Settings panel (hidden, shown as popup)."""
        self.settings_visible = False
        
        self.settings_popup = tk.Frame(self.root, bg=T.BG_SURFACE)
        
        inner = tk.Frame(self.settings_popup, bg=T.BG_SURFACE)
        inner.pack(fill="both", expand=True, padx=T.S3, pady=T.S3)
        
        # Title
        tk.Label(inner, text="Scan Settings", font=T.FONT_HEADING,
                bg=T.BG_SURFACE, fg=T.TEXT_PRIMARY).pack(anchor="w", pady=(0, T.S3))
        
        # Color mode
        tk.Label(inner, text="Color Mode", font=T.FONT_LABEL,
                bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY).pack(anchor="w")
        
        self.color_var = tk.StringVar(value="Color")
        PillToggle(inner, self.color_var, ["Color", "Gray", "B&W"], width=180).pack(anchor="w", pady=(T.S1, T.S3))
        
        # Brightness
        tk.Label(inner, text="Brightness", font=T.FONT_LABEL,
                bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY).pack(anchor="w")
        self.brightness_var = tk.IntVar(value=0)
        SoftSlider(inner, self.brightness_var, width=180).pack(anchor="w", pady=(T.S1, T.S3))
        
        # Contrast
        tk.Label(inner, text="Contrast", font=T.FONT_LABEL,
                bg=T.BG_SURFACE, fg=T.TEXT_SECONDARY).pack(anchor="w")
        self.contrast_var = tk.IntVar(value=0)
        SoftSlider(inner, self.contrast_var, width=180).pack(anchor="w", pady=(T.S1, T.S3))
        
        # Resolution note
        tk.Label(inner, text=f"Resolution: {SCAN_DPI} DPI", font=T.FONT_SMALL,
                bg=T.BG_SURFACE, fg=T.TEXT_MUTED).pack(anchor="w", pady=(T.S2, 0))
        
        # Clear all (destructive, at bottom)
        WarmButton(inner, "Clear All Pages", self._on_clear_all,
                  primary=False, width=160, height=36).pack(anchor="w", pady=(T.S4, 0))
    
    def _toggle_settings(self):
        if self.settings_visible:
            self.settings_popup.place_forget()
            self.settings_visible = False
        else:
            # Position below settings button
            self.settings_popup.place(relx=1.0, y=T.TOOLBAR_H, anchor="ne", x=-T.S4)
            self.settings_visible = True
    
    # ══════════════════════════════════════════════════════════════════════════
    # THUMBNAILS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _refresh_strip(self):
        for w in self.strip_inner.winfo_children():
            w.destroy()
        self._thumb_refs.clear()
        
        if not self.pages:
            self._update_preview()
            return
        
        for i, page in enumerate(self.pages):
            thumb = PaperThumbnail(
                self.strip_inner, page, i,
                is_selected=(i == self.selected_index),
                on_select=self._select_page,
                on_rotate=self._rotate_page
            )
            thumb.pack(side="left", padx=T.S2, pady=T.S1)
            self._thumb_refs.append(thumb)
        
        self._update_preview()
    
    def _select_page(self, index):
        self.selected_index = index
        self._refresh_strip()
    
    def _rotate_page(self, index):
        if 0 <= index < len(self.pages):
            self.pages[index].rotate()
            self._refresh_strip()
    
    # ══════════════════════════════════════════════════════════════════════════
    # PREVIEW
    # ══════════════════════════════════════════════════════════════════════════
    
    def _update_preview(self):
        if not self.pages:
            self.preview_label.configure(image="", text="Scan your first page to begin")
            self._preview_image = None
            return
        
        idx = self.selected_index if self.selected_index >= 0 else len(self.pages) - 1
        if idx < 0 or idx >= len(self.pages):
            return
        
        page = self.pages[idx]
        
        pw = self.preview_container.winfo_width()
        ph = self.preview_container.winfo_height()
        if pw < 50 or ph < 50:
            return
        
        # Leave room for "shadow"
        max_w = min(pw - T.S6, int(ph * 0.7))
        max_h = ph - T.S5
        
        img = page.image.copy()
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        
        # Add paper shadow effect
        shadow_offset = 6
        shadow_img = Image.new("RGBA", (img.width + shadow_offset + 4, img.height + shadow_offset + 4), T.BG_BASE)
        
        # Draw shadow rectangle
        draw = ImageDraw.Draw(shadow_img)
        draw.rectangle(
            [shadow_offset, shadow_offset, img.width + shadow_offset, img.height + shadow_offset],
            fill="#00000020"
        )
        
        # Paste original on top
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        shadow_img.paste(img, (0, 0))
        
        self._preview_image = ImageTk.PhotoImage(shadow_img)
        self.preview_label.configure(image=self._preview_image, text="")
    
    # ══════════════════════════════════════════════════════════════════════════
    # SCANNING
    # ══════════════════════════════════════════════════════════════════════════
    
    def _get_scanner_device(self):
        import win32com.client
        dm = win32com.client.Dispatch("WIA.DeviceManager")
        for i in range(1, dm.DeviceInfos.Count + 1):
            info = dm.DeviceInfos.Item(i)
            if info.Type == WIA_DEVICE_TYPE_SCANNER:
                return info.Connect()
        raise RuntimeError("No scanner found.")
    
    def _configure_scan_item(self, item):
        color_map = {"Color": 1, "Gray": 2, "B&W": 4}
        
        def _set(pid, val):
            try:
                for j in range(1, item.Properties.Count + 1):
                    p = item.Properties.Item(j)
                    if p.PropertyID == pid:
                        p.Value = val
                        return
            except:
                pass
        
        _set(WIA_IPS_CUR_INTENT, color_map.get(self.color_var.get(), 1))
        _set(WIA_IPS_XRES, SCAN_DPI)
        _set(WIA_IPS_YRES, SCAN_DPI)
        _set(WIA_IPS_BRIGHTNESS, self.brightness_var.get())
        _set(WIA_IPS_CONTRAST, self.contrast_var.get())
    
    def _on_scan_page(self):
        if self.scanning:
            return
        self.scanning = True
        self.scan_btn.set_disabled(True)
        threading.Thread(target=self._scan_thread, daemon=True).start()
    
    def _scan_thread(self):
        co_initialized = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            co_initialized = True
            
            device = self._get_scanner_device()
            item = device.Items(1)
            self._configure_scan_item(item)
            img_file = item.Transfer(WIA_IMG_FORMAT_BMP)
            img = Image.open(io.BytesIO(img_file.FileData.BinaryData))
            
            self.page_counter += 1
            page = ScannedPage(img, self.page_counter)
            
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"scan_{ts}_{self.page_counter:03d}"
            img.save(os.path.join(SCANS_DIR, f"{base}.png"), "PNG")
            
            pdf_img = img.convert("RGB") if img.mode != "RGB" else img
            pdf_img.save(os.path.join(PDF_DIR, f"{base}.pdf"), "PDF")
            
            self.root.after(0, self._add_page, page)
        except Exception as e:
            self.root.after(0, lambda err=str(e): messagebox.showerror("Scan Error", err))
        finally:
            if co_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            self.root.after(0, self._scan_done)
    
    def _add_page(self, page):
        self.pages.append(page)
        self.selected_index = len(self.pages) - 1
        self._refresh_strip()
    
    def _scan_done(self):
        self.scanning = False
        self.scan_btn.set_disabled(False)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SAVE
    # ══════════════════════════════════════════════════════════════════════════
    
    def _on_save(self):
        if not self.pages:
            messagebox.showinfo("Save", "No pages to save.")
            return
        
        fmt = self.format_var.get()
        if fmt == "PDF":
            self._save_pdf()
        else:
            ext = ".png" if fmt == "PNG" else ".jpg"
            self._save_images(fmt if fmt == "PNG" else "JPEG", ext)
    
    def _save_pdf(self):
        path = filedialog.asksaveasfilename(
            title="Save PDF", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], initialdir=PDF_DIR
        )
        if not path:
            return
        try:
            images = [p.image.convert("RGB") if p.image.mode != "RGB" else p.image.copy()
                     for p in self.pages]
            if len(images) == 1:
                images[0].save(path, "PDF")
            else:
                images[0].save(path, "PDF", save_all=True, append_images=images[1:])
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
    
    def _save_images(self, fmt, ext):
        if len(self.pages) == 1:
            path = filedialog.asksaveasfilename(
                title=f"Save {fmt}", defaultextension=ext,
                filetypes=[(fmt, f"*{ext}")], initialdir=SCANS_DIR
            )
            if path:
                try:
                    self.pages[0].image.save(path, fmt)
                except Exception as e:
                    messagebox.showerror("Save Error", str(e))
        else:
            folder = filedialog.askdirectory(title="Choose folder", initialdir=SCANS_DIR)
            if folder:
                try:
                    for i, page in enumerate(self.pages):
                        page.image.save(os.path.join(folder, f"page_{i+1:03d}{ext}"), fmt)
                except Exception as e:
                    messagebox.showerror("Save Error", str(e))
    
    def _on_clear_all(self):
        if self.pages and messagebox.askyesno("Clear All", "Remove all scanned pages?"):
            self.pages.clear()
            self.selected_index = -1
            self.page_counter = 0
            self._refresh_strip()
            self.settings_visible = False
            self.settings_popup.place_forget()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    ScannerAppV4(root)
    root.mainloop()


if __name__ == "__main__":
    main()
