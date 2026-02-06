import math
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

from genimail.domain.helpers import parse_length_to_inches

_STALE = object()
UNIT_CHOICES = ("ft", "in", "mm", "cm", "m")


def _now_ts() -> int:
    return int(time.time())


def format_inches(value_in: float) -> str:
    if value_in is None or not math.isfinite(value_in):
        return ""
    sign = "-" if value_in < 0 else ""
    value_in = abs(value_in)
    feet = int(value_in // 12)
    inches = value_in - feet * 12
    # Round to 1/8" for display (measurement is inherently approximate).
    inches = round(inches * 8) / 8.0
    if inches >= 12:
        feet += 1
        inches -= 12
    if feet:
        if inches:
            # Trim .0
            inch_str = str(int(inches)) if abs(inches - int(inches)) < 1e-9 else str(inches)
            return f"{sign}{feet}' {inch_str}\""
        return f"{sign}{feet}'"
    inch_str = str(int(inches)) if abs(inches - int(inches)) < 1e-9 else str(inches)
    return f"{sign}{inch_str}\""


class _LRU:
    def __init__(self, max_items: int = 8):
        self.max_items = max_items
        self._d = OrderedDict()

    def get(self, key):
        v = self._d.get(key)
        if v is None:
            return None
        self._d.move_to_end(key)
        return v

    def put(self, key, value):
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self.max_items:
            self._d.popitem(last=False)

    def clear(self):
        self._d.clear()


@dataclass(frozen=True)
class Segment:
    page_index: int
    x0_pt: float
    y0_pt: float
    x1_pt: float
    y1_pt: float
    length_pdf_inches: float


class PdfViewerFrame(ttk.Frame):
    """
    Embedded PDF viewer optimized for interactive measurement:
      - fast MuPDF rendering (PyMuPDF)
      - annotations off by default
      - background render + small LRU cache
      - ruler + per-PDF calibration
      - manual wall segment accumulation -> sqft
    """

    MAX_PIXELS = 40_000_000  # clamp huge renders (memory safety)

    def __init__(
        self,
        parent,
        *,
        config_get,
        config_set,
        initial_dir=None,
        bg="#ffffff",
        accent="#0078d4",
    ):
        super().__init__(parent)
        self._config_get = config_get
        self._config_set = config_set
        self._initial_dir = initial_dir
        self._bg = bg
        self._accent = accent

        self._doc = None
        self._doc_key = None
        self._doc_name = ""
        self._page_index = 0
        self._page_count = 0
        self._doc_gen = 0
        self._doc_lock = threading.Lock()
        self._page_rect_cache = {}
        self._syncing_page_scale = False

        self._fit_width = tk.BooleanVar(value=True)
        self._render_annots = tk.BooleanVar(value=False)
        self._zoom = 1.0
        self._current_scale = None  # points -> pixels

        self._render_job_id = 0
        self._render_after_id = None
        self._cache = _LRU(max_items=10)

        # Measurement state
        self._tool = tk.StringVar(value="ruler")  # ruler | calibrate
        self._cal_factor = 1.0
        self._has_cal = False
        self._last_measure_inches = None
        self._last_line = None  # (x0_pt, y0_pt, x1_pt, y1_pt, length_pdf_inches, page_index)
        self._last_line_mode = None  # "ruler" | "calibrate"
        self._drag = None  # (x0,y0,line_id)
        self._temp_line_id = None
        self._show_lines = tk.BooleanVar(value=True)
        self._segments: list[Segment] = []
        self._seg_line_ids: list[int] = []

        self._build_ui()
        self._set_enabled(False)

    # ------------------------------------------------------------ Public
    def load_pdf_bytes(self, doc_key: str, name: str, pdf_bytes: bytes):
        if not fitz or Image is None or ImageTk is None:
            messagebox.showerror(
                "Missing Dependency",
                "PDF viewing requires Pillow + PyMuPDF.\n\nInstall with:\n  pip install pillow PyMuPDF",
                parent=self.winfo_toplevel(),
            )
            return

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            messagebox.showerror("PDF Error", f"Could not open PDF:\n{e}", parent=self.winfo_toplevel())
            return

        self._set_doc(doc, doc_key=doc_key, name=name or "attachment.pdf")

    def load_pdf_file(self, path: str):
        if not fitz or Image is None or ImageTk is None:
            messagebox.showerror(
                "Missing Dependency",
                "PDF viewing requires Pillow + PyMuPDF.\n\nInstall with:\n  pip install pillow PyMuPDF",
                parent=self.winfo_toplevel(),
            )
            return
        try:
            doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror("PDF Error", f"Could not open PDF:\n{e}", parent=self.winfo_toplevel())
            return

        st = os.stat(path)
        doc_key = f"file:{os.path.abspath(path)}:{int(st.st_mtime)}:{st.st_size}"
        self._set_doc(doc, doc_key=doc_key, name=os.path.basename(path))

    # ------------------------------------------------------------ UI
    def _build_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Button(toolbar, text="Open PDF...", command=self._on_open_local).pack(side="left")

        self.doc_lbl = ttk.Label(toolbar, text="No PDF loaded", width=40)
        self.doc_lbl.pack(side="left", padx=(10, 8))

        nav = ttk.Frame(toolbar)
        nav.pack(side="left")
        ttk.Button(nav, text="Prev", width=6, command=lambda: self._goto_page(self._page_index - 1)).pack(side="left")
        ttk.Button(nav, text="Next", width=6, command=lambda: self._goto_page(self._page_index + 1)).pack(side="left", padx=(4, 0))
        ttk.Label(nav, text="Page").pack(side="left", padx=(10, 4))
        self.page_entry = ttk.Entry(nav, width=5)
        self.page_entry.pack(side="left")
        self.page_entry.bind("<Return>", lambda e: self._on_page_entry())
        self.page_total_lbl = ttk.Label(nav, text="/ 0")
        self.page_total_lbl.pack(side="left", padx=(4, 0))
        self.page_scale = ttk.Scale(nav, from_=1, to=1, orient="horizontal", length=140, command=self._on_page_scale)
        self.page_scale.pack(side="left", padx=(10, 0))

        zoom = ttk.Frame(toolbar)
        zoom.pack(side="left", padx=(12, 0))
        ttk.Checkbutton(zoom, text="Fit Width", variable=self._fit_width, command=self._on_fit_toggle).pack(side="left")
        ttk.Button(zoom, text="-", width=3, command=lambda: self._zoom_by(1 / 1.25)).pack(side="left", padx=(6, 0))
        ttk.Button(zoom, text="+", width=3, command=lambda: self._zoom_by(1.25)).pack(side="left", padx=(3, 0))
        ttk.Button(zoom, text="Reset View", command=self._reset_view).pack(side="left", padx=(6, 0))

        ttk.Checkbutton(toolbar, text="Render annotations", variable=self._render_annots, command=self._render_debounced).pack(
            side="right"
        )

        self.status_lbl = ttk.Label(self, text="", foreground="#555555")
        self.status_lbl.pack(fill="x", padx=8, pady=(0, 6))

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Viewer (canvas + scrollbars)
        viewer = ttk.Frame(paned)
        paned.add(viewer, weight=4)

        self.canvas = tk.Canvas(viewer, bg=self._bg, highlightthickness=1, highlightbackground="#cccccc")
        vsb = ttk.Scrollbar(viewer, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(viewer, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        viewer.rowconfigure(0, weight=1)
        viewer.columnconfigure(0, weight=1)

        self.canvas.bind("<Configure>", lambda e: self._on_canvas_resize())
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Tools panel
        tools = ttk.Frame(paned)
        paned.add(tools, weight=1)

        meas = ttk.LabelFrame(tools, text="Measurement", padding=8)
        meas.pack(fill="x", pady=(0, 8))

        ttk.Label(meas, text="Tool:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(meas, text="Ruler", variable=self._tool, value="ruler").grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Radiobutton(meas, text="Calibrate", variable=self._tool, value="calibrate").grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )

        self.cal_lbl = ttk.Label(meas, text="Calibration: none")
        self.cal_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.meas_lbl = ttk.Label(meas, text="Last: -")
        self.meas_lbl.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Button(meas, text="Add Segment", command=self._add_segment).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Checkbutton(meas, text="Show lines", variable=self._show_lines, command=self._redraw_segments).grid(
            row=3, column=2, sticky="e", pady=(8, 0)
        )
        ttk.Label(meas, text="Calib bare number unit:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.cal_input_unit_var = tk.StringVar(value="ft")
        self.cal_input_unit_combo = ttk.Combobox(
            meas, textvariable=self.cal_input_unit_var, values=list(UNIT_CHOICES), state="readonly", width=6
        )
        self.cal_input_unit_combo.grid(row=4, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        walls = ttk.LabelFrame(tools, text="Wall Sqft", padding=8)
        walls.pack(fill="both", expand=True)

        ttk.Label(walls, text="Wall height:").grid(row=0, column=0, sticky="w")
        self.height_entry = ttk.Entry(walls, width=10)
        self.height_entry.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.height_entry.insert(0, "8ft")
        self.height_entry.bind("<KeyRelease>", lambda e: self._update_totals())
        self.height_input_unit_var = tk.StringVar(value="ft")
        self.height_input_unit_combo = ttk.Combobox(
            walls, textvariable=self.height_input_unit_var, values=list(UNIT_CHOICES), state="readonly", width=6
        )
        self.height_input_unit_combo.grid(row=0, column=2, sticky="w", padx=(6, 0))
        self.height_input_unit_combo.bind("<<ComboboxSelected>>", lambda e: self._update_totals())
        ttk.Label(walls, text="(bare number unit)").grid(row=0, column=3, sticky="w", padx=(6, 0))
        ttk.Label(walls, text="Examples: 8ft, 96in, 2400mm, 2.4m", foreground="#666666").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(3, 0)
        )

        self.total_lin_lbl = ttk.Label(walls, text="Total linear: 0 ft")
        self.total_lin_lbl.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.total_sqft_lbl = ttk.Label(walls, text="Total area: 0 sqft")
        self.total_sqft_lbl.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self.math_lbl = ttk.Label(walls, text="", foreground="#555555")
        self.math_lbl.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

        ttk.Label(walls, text="Segments:").grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.seg_list = tk.Listbox(walls, height=8)
        self.seg_list.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=(4, 0))

        seg_btns = ttk.Frame(walls)
        seg_btns.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Button(seg_btns, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(seg_btns, text="Clear", command=self._clear_segments).pack(side="left", padx=(6, 0))

        walls.rowconfigure(6, weight=1)
        walls.columnconfigure(1, weight=1)

        # Current rendered image reference
        self._photo = None
        self._img_item = None

    def _set_enabled(self, enabled: bool):
        base_state = "normal" if enabled else "disabled"
        for w in (self.page_entry, self.page_scale, self.height_entry, self.seg_list):
            try:
                w.configure(state=base_state)
            except Exception:
                pass
        combo_state = "readonly" if enabled else "disabled"
        for w in (self.cal_input_unit_combo, self.height_input_unit_combo):
            try:
                w.configure(state=combo_state)
            except Exception:
                pass

    # ------------------------------------------------------------ Doc lifecycle
    def _set_doc(self, doc, *, doc_key: str, name: str):
        old = None
        with self._doc_lock:
            old = self._doc
            self._doc = doc
            self._doc_gen += 1
        try:
            if old is not None:
                old.close()
        except Exception:
            pass

        self._doc_key = doc_key
        self._doc_name = name
        self._page_count = int(getattr(doc, "page_count", 0) or 0)
        self._page_index = 0
        self._cache.clear()
        self._page_rect_cache.clear()
        self._segments.clear()
        self._last_line = None
        self.seg_list.delete(0, tk.END)
        self._last_measure_inches = None
        self._clear_temp_line()
        self._clear_segment_lines()

        self.doc_lbl.configure(text=name)
        self.page_total_lbl.configure(text=f"/ {self._page_count}")
        self.page_entry.delete(0, tk.END)
        self.page_entry.insert(0, "1")
        self.page_scale.configure(to=max(1, self._page_count))
        self._set_page_scale_value(1)

        self._load_calibration()
        self._set_enabled(True)
        self._render_debounced()
        self._update_totals()

    def _load_calibration(self):
        self._has_cal = False
        self._cal_factor = 1.0
        if not self._doc_key:
            self.cal_lbl.configure(text="Calibration: none")
            return
        data = self._config_get("pdf_calibration", {}) or {}
        entry = data.get(self._doc_key) or {}
        try:
            cf = float(entry.get("cal_factor", 1.0))
            if math.isfinite(cf) and cf > 0:
                self._cal_factor = cf
                self._has_cal = True
        except Exception:
            pass
        if self._has_cal:
            self.cal_lbl.configure(text=f"Calibration: x{self._cal_factor:.4f}")
        else:
            self.cal_lbl.configure(text="Calibration: none (use Calibrate tool)")
        # Calibration affects displayed totals/segment labels.
        self._rebuild_segment_list()
        self._update_totals()

    def _save_calibration(self, cal_factor: float):
        if not self._doc_key:
            return
        data = self._config_get("pdf_calibration", {}) or {}
        data[self._doc_key] = {"cal_factor": float(cal_factor), "updated_at": _now_ts()}
        self._config_set("pdf_calibration", data)
        self._load_calibration()

    # ------------------------------------------------------------ Actions
    def _on_open_local(self):
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=self._initial_dir or os.getcwd(),
            parent=self.winfo_toplevel(),
        )
        if not path:
            return
        self.load_pdf_file(path)

    def _on_page_entry(self):
        try:
            idx = int(self.page_entry.get().strip()) - 1
        except Exception:
            return
        self._goto_page(idx)

    def _on_page_scale(self, value):
        if self._syncing_page_scale:
            return
        try:
            page_one_based = int(round(float(value)))
        except Exception:
            return
        self._goto_page(page_one_based - 1, from_scale=True)

    def _set_page_scale_value(self, page_one_based: int):
        self._syncing_page_scale = True
        try:
            self.page_scale.set(page_one_based)
        finally:
            self._syncing_page_scale = False

    def _goto_page(self, idx: int, from_scale: bool = False):
        if not self._doc:
            return
        idx = max(0, min(idx, self._page_count - 1))
        if idx == self._page_index:
            if not from_scale:
                self._set_page_scale_value(idx + 1)
            return
        self._page_index = idx
        self.page_entry.delete(0, tk.END)
        self.page_entry.insert(0, str(idx + 1))
        if not from_scale:
            self._set_page_scale_value(idx + 1)
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
        self._render_debounced()

    def _on_fit_toggle(self):
        if self._fit_width.get():
            self._render_debounced()

    def _zoom_by(self, factor: float):
        self._fit_width.set(False)
        self._zoom = max(0.2, min(self._zoom * factor, 8.0))
        self._render_debounced()

    def _reset_view(self):
        self._fit_width.set(True)
        self._zoom = 1.0
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
        self._render_debounced()

    # ------------------------------------------------------------ Rendering
    def _on_canvas_resize(self):
        if self._fit_width.get() and self._doc:
            # Debounce resize thrash.
            self._render_debounced()

    def _render_debounced(self):
        if self._render_after_id is not None:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
        self._render_after_id = self.after(120, self._render_now)

    def _render_now(self):
        self._render_after_id = None
        if not self._doc:
            return

        rect = self._get_page_rect(self._page_index)

        if self._fit_width.get() and rect is not None:
            # scale = target_px / page_width_points
            target = max(200, self.canvas.winfo_width() - 20)
            scale = max(0.2, min(target / max(1.0, rect.width), 8.0))
        else:
            scale = self._zoom

        # Clamp insane renders for memory safety.
        if rect is not None:
            max_scale = math.sqrt(self.MAX_PIXELS / max(1.0, rect.width * rect.height))
            scale = min(scale, max_scale)

        # Bucket scale to stabilize caching and UI thrash.
        scale = round(scale * 20) / 20.0  # 0.05 steps
        scale = max(0.2, min(scale, 8.0))

        cache_key = (self._doc_key, self._page_index, scale, bool(self._render_annots.get()))
        cached = self._cache.get(cache_key)
        if cached is not None:
            photo, used_scale = cached
            self._current_scale = used_scale
            self._display_photo(photo, from_cache=True)
            return

        self._render_job_id += 1
        job_id = self._render_job_id
        doc_gen = self._doc_gen
        page_index = self._page_index
        annots = bool(self._render_annots.get())
        self.status_lbl.configure(text="Rendering...")

        def work():
            try:
                with self._doc_lock:
                    if doc_gen != self._doc_gen or self._doc is None:
                        return _STALE
                    p = self._doc.load_page(page_index)
                    mat = fitz.Matrix(scale, scale)
                    pix = p.get_pixmap(matrix=mat, annots=annots, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                return scale, img
            except Exception as e:
                return e

        def on_done(result):
            if job_id != self._render_job_id:
                return  # stale
            if result is _STALE:
                return
            if isinstance(result, Exception):
                self.status_lbl.configure(text=f"Render error: {result}")
                return
            used_scale, pil_img = result
            if job_id != self._render_job_id:
                return
            try:
                photo = ImageTk.PhotoImage(pil_img)
            except Exception as e:
                self.status_lbl.configure(text=f"Render error: {e}")
                return

            self._current_scale = used_scale
            self._cache.put(cache_key, (photo, used_scale))
            self._display_photo(photo, from_cache=False)
            self.status_lbl.configure(text="")

        def run_and_callback():
            res = work()
            self.after(0, lambda: on_done(res))

        threading.Thread(target=run_and_callback, daemon=True).start()

    def _get_page_rect(self, page_index: int):
        rect = self._page_rect_cache.get(page_index)
        if rect is not None:
            return rect
        try:
            with self._doc_lock:
                if self._doc is None:
                    return None
                rect = self._doc.load_page(page_index).rect
        except Exception:
            rect = None
        self._page_rect_cache[page_index] = rect
        return rect

    def _display_photo(self, photo, *, from_cache: bool):
        self._photo = photo  # prevent GC
        if self._img_item is None:
            self._img_item = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._img_item, image=self._photo)
        # Reset scroll region to image bounds.
        self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
        # Redraw overlays in the new scale (or clear them if hidden).
        self._redraw_segments()
        if not from_cache:
            self._clear_temp_line()

    # ------------------------------------------------------------ Measurement
    def _clear_temp_line(self):
        if self._temp_line_id is None:
            self._drag = None
            return
        try:
            self.canvas.delete(self._temp_line_id)
        except Exception:
            pass
        self._temp_line_id = None
        self._drag = None

    def _clear_segment_lines(self):
        for lid in self._seg_line_ids:
            try:
                self.canvas.delete(lid)
            except Exception:
                pass
        self._seg_line_ids.clear()

    def _redraw_segments(self):
        self._clear_segment_lines()
        if not self._show_lines.get() or self._current_scale is None:
            return
        scale = float(self._current_scale)
        page = int(self._page_index)
        for seg in self._segments:
            if seg.page_index != page:
                continue
            x0 = seg.x0_pt * scale
            y0 = seg.y0_pt * scale
            x1 = seg.x1_pt * scale
            y1 = seg.y1_pt * scale
            try:
                lid = self.canvas.create_line(x0, y0, x1, y1, fill=self._accent, width=2)
                self._seg_line_ids.append(lid)
            except Exception:
                pass

    def _on_mouse_down(self, event):
        if not self._doc or self._photo is None:
            return
        tool = self._tool.get()
        if tool not in ("ruler", "calibrate"):
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self._clear_temp_line()
        self._temp_line_id = self.canvas.create_line(x, y, x, y, fill=self._accent, width=2)
        self._drag = (x, y, self._temp_line_id)

    def _on_mouse_drag(self, event):
        if self._drag is None:
            return
        x0, y0, line_id = self._drag
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)
        try:
            self.canvas.coords(line_id, x0, y0, x1, y1)
        except Exception:
            pass

    def _on_mouse_up(self, event):
        if self._drag is None or self._current_scale is None:
            return
        x0, y0, line_id = self._drag
        x1 = self.canvas.canvasx(event.x)
        y1 = self.canvas.canvasy(event.y)
        self._drag = None

        dx = x1 - x0
        dy = y1 - y0
        px_len = math.hypot(dx, dy)
        if px_len < 2:
            self._clear_temp_line()
            return

        scale = max(1e-6, float(self._current_scale))
        x0_pt = x0 / scale
        y0_pt = y0 / scale
        x1_pt = x1 / scale
        y1_pt = y1 / scale
        pdf_points = math.hypot(x1_pt - x0_pt, y1_pt - y0_pt)
        pdf_inches = pdf_points / 72.0
        tool = self._tool.get()
        self._last_line_mode = tool
        self._last_line = (x0_pt, y0_pt, x1_pt, y1_pt, pdf_inches, int(self._page_index))

        if tool == "calibrate":
            self._clear_temp_line()
            self._prompt_calibration(pdf_inches)
            return

        real_inches = pdf_inches * (self._cal_factor if self._has_cal else 1.0)
        self._last_measure_inches = real_inches
        label = format_inches(real_inches)
        if self._has_cal:
            self.meas_lbl.configure(text=f"Last: {label} (calibrated)")
        else:
            self.meas_lbl.configure(text=f"Last: {label} (uncalibrated)")

        # Temp line is just a preview; don't accumulate canvas items.
        self._clear_temp_line()

    def _prompt_calibration(self, pdf_inches: float):
        top = self.winfo_toplevel()
        raw = simpledialog.askstring(
            "Calibration",
            "Enter real-world length (examples: 10ft 6in, 2500mm, 2.4m).\n"
            f"Bare numbers use: {self.cal_input_unit_var.get()}",
            parent=top,
        )
        if raw is None:
            return
        try:
            real_inches = parse_length_to_inches(raw, default_unit=self.cal_input_unit_var.get())
            if real_inches <= 0 or not math.isfinite(real_inches):
                raise ValueError("Length must be > 0.")
        except Exception as e:
            messagebox.showerror("Invalid Length", str(e), parent=top)
            return

        if pdf_inches <= 0 or not math.isfinite(pdf_inches):
            messagebox.showerror("Calibration Error", "Invalid PDF length.", parent=top)
            return

        cal_factor = real_inches / pdf_inches
        if not math.isfinite(cal_factor) or cal_factor <= 0:
            messagebox.showerror("Calibration Error", "Could not compute calibration factor.", parent=top)
            return

        self._save_calibration(cal_factor)
        self._last_measure_inches = real_inches
        self.meas_lbl.configure(text=f"Last: {format_inches(real_inches)} (calibrated)")
        # Do not keep calibration lines on the canvas (speed / cleanliness).
        self._clear_temp_line()

    # ------------------------------------------------------------ Wall sqft
    def _add_segment(self):
        if not self._last_line:
            return
        if self._last_line_mode != "ruler":
            messagebox.showinfo("Add Segment", "Switch to Ruler and draw a line to add a segment.", parent=self.winfo_toplevel())
            return
        x0_pt, y0_pt, x1_pt, y1_pt, pdf_inches, page_index = self._last_line
        if not math.isfinite(pdf_inches) or pdf_inches <= 0:
            return
        seg = Segment(
            page_index=int(page_index),
            x0_pt=float(x0_pt),
            y0_pt=float(y0_pt),
            x1_pt=float(x1_pt),
            y1_pt=float(y1_pt),
            length_pdf_inches=float(pdf_inches),
        )
        self._segments.append(seg)
        # Prevent accidental double-add.
        self._last_line = None
        self._last_line_mode = None
        self._rebuild_segment_list()
        self._redraw_segments()
        self._update_totals()

    def _remove_selected(self):
        sel = self.seg_list.curselection()
        if not sel:
            return
        i = int(sel[0])
        try:
            self._segments.pop(i)
        except Exception:
            return
        self._rebuild_segment_list()
        self._redraw_segments()
        self._update_totals()

    def _clear_segments(self):
        self._segments.clear()
        self.seg_list.delete(0, tk.END)
        self._clear_segment_lines()
        self._update_totals()

    def _rebuild_segment_list(self):
        self.seg_list.delete(0, tk.END)
        cal = self._cal_factor if self._has_cal else 1.0
        for i, seg in enumerate(self._segments, start=1):
            real_in = seg.length_pdf_inches * cal
            self.seg_list.insert(tk.END, f"{i:02d}. p{seg.page_index + 1}: {format_inches(real_in)}")

    def _update_totals(self):
        cal = self._cal_factor if self._has_cal else 1.0
        total_inches = sum(s.length_pdf_inches * cal for s in self._segments) if self._segments else 0.0
        total_ft = total_inches / 12.0
        self.total_lin_lbl.configure(text=f"Total linear: {total_ft:.2f} ft")

        try:
            h_in = parse_length_to_inches(self.height_entry.get(), default_unit=self.height_input_unit_var.get())
            h_ft = h_in / 12.0
        except Exception:
            h_ft = 0.0

        sqft = total_ft * h_ft
        self.total_sqft_lbl.configure(text=f"Total area: {sqft:.2f} sqft")
        if h_ft > 0:
            self.math_lbl.configure(text=f"Math: {total_ft:.2f} ft x {h_ft:.2f} ft = {sqft:.2f} sqft")
        else:
            self.math_lbl.configure(text="Math: set a wall height to compute sqft")
