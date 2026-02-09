import hashlib
import math

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

try:
    import fitz

    HAS_FITZ = True
except Exception:
    fitz = None
    HAS_FITZ = False

PDF_RENDER_DPI = 150
VERTEX_DOT_RADIUS = 4
VERTEX_DOT_COLOR = Qt.red
EDGE_LINE_COLOR = Qt.blue
EDGE_LINE_WIDTH = 2
ZOOM_FACTOR = 1.25


class PdfGraphicsView(QGraphicsView):
    """PyMuPDF + QGraphicsView PDF renderer with mouse coordinate mapping."""

    pageChanged = Signal(int, int)  # (current_page_0based, total_pages)
    pointClicked = Signal(float, float)  # (x_pdf_pts, y_pdf_pts)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self._doc = None
        self._current_page = 0
        self._pixmap_item = None
        self._scale = 1.0  # pts-to-pixels ratio for current render
        self._overlay_items = []
        self._click_enabled = False
        self._doc_path = None
        self._doc_bytes_hash = None

    # ── Public API ───────────────────────────────────────────────

    def open_document(self, path):
        if not HAS_FITZ:
            raise RuntimeError("PyMuPDF (fitz) is required for PDF rendering.")
        doc = fitz.open(path)
        self._doc = doc
        self._doc_path = path
        self._doc_bytes_hash = None
        self._current_page = 0
        self._render_page(0)
        self._fit_to_width()

    def open_bytes(self, data: bytes):
        if not HAS_FITZ:
            raise RuntimeError("PyMuPDF (fitz) is required for PDF rendering.")
        doc = fitz.open(stream=data, filetype="pdf")
        self._doc = doc
        self._doc_path = None
        self._doc_bytes_hash = hashlib.md5(data[:4096]).hexdigest()
        self._current_page = 0
        self._render_page(0)
        self._fit_to_width()

    @property
    def doc_key(self):
        if self._doc_path:
            return f"file:{self._doc_path}"
        if self._doc_bytes_hash:
            return f"bytes:{self._doc_bytes_hash}"
        return None

    @property
    def page_count(self):
        return len(self._doc) if self._doc else 0

    @property
    def current_page(self):
        return self._current_page

    def set_click_enabled(self, enabled):
        self._click_enabled = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.unsetCursor()

    # ── Page navigation ──────────────────────────────────────────

    def go_to_page(self, n):
        if not self._doc or n < 0 or n >= len(self._doc):
            return
        self._current_page = n
        self._render_page(n)
        self.pageChanged.emit(n, len(self._doc))

    def next_page(self):
        self.go_to_page(self._current_page + 1)

    def prev_page(self):
        self.go_to_page(self._current_page - 1)

    # ── Zoom ─────────────────────────────────────────────────────

    def zoom_in(self):
        self.scale(ZOOM_FACTOR, ZOOM_FACTOR)

    def zoom_out(self):
        self.scale(1.0 / ZOOM_FACTOR, 1.0 / ZOOM_FACTOR)

    def fit_width(self):
        self._fit_to_width()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # ── Mouse → PDF coords ───────────────────────────────────────

    def mousePressEvent(self, event):
        if self._click_enabled and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            if self._pixmap_item and self._scale > 0:
                x_pt = scene_pos.x() / self._scale
                y_pt = scene_pos.y() / self._scale
                self.pointClicked.emit(x_pt, y_pt)
                event.accept()
                return
        super().mousePressEvent(event)

    # ── Polygon overlay ──────────────────────────────────────────

    def add_vertex_dot(self, x_pt, y_pt):
        r = VERTEX_DOT_RADIUS
        sx = x_pt * self._scale
        sy = y_pt * self._scale
        dot = QGraphicsEllipseItem(sx - r, sy - r, r * 2, r * 2)
        dot.setBrush(VERTEX_DOT_COLOR)
        dot.setPen(QPen(Qt.NoPen))
        self._scene.addItem(dot)
        self._overlay_items.append(dot)
        return dot

    def add_edge_line(self, x0, y0, x1, y1):
        pen = QPen(EDGE_LINE_COLOR, EDGE_LINE_WIDTH, Qt.DashLine)
        line = QGraphicsLineItem(
            x0 * self._scale, y0 * self._scale,
            x1 * self._scale, y1 * self._scale,
        )
        line.setPen(pen)
        self._scene.addItem(line)
        self._overlay_items.append(line)
        return line

    def clear_overlays(self):
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

    def redraw_overlays(self, points):
        self.clear_overlays()
        for x, y in points:
            self.add_vertex_dot(x, y)
        for i in range(1, len(points)):
            x0, y0 = points[i - 1]
            x1, y1 = points[i]
            self.add_edge_line(x0, y0, x1, y1)

    # ── Internal ─────────────────────────────────────────────────

    def _render_page(self, page_index):
        if not self._doc or page_index < 0 or page_index >= len(self._doc):
            return
        page = self._doc[page_index]
        zoom = PDF_RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        self._scale = zoom  # pts * scale = pixels

        if pix.alpha:
            fmt = QImage.Format_RGBA8888
        else:
            fmt = QImage.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        qpixmap = QPixmap.fromImage(qimg)

        self._scene.clear()
        self._overlay_items.clear()
        self._pixmap_item = self._scene.addPixmap(qpixmap)
        self._scene.setSceneRect(QRectF(qpixmap.rect()))

    def _fit_to_width(self):
        if not self._pixmap_item:
            return
        scene_rect = self._scene.sceneRect()
        if scene_rect.width() <= 0:
            return
        self.resetTransform()
        view_width = self.viewport().width()
        scale = view_width / scene_rect.width()
        self.scale(scale, scale)

    def close_document(self):
        if self._doc:
            self._doc.close()
            self._doc = None
        self._scene.clear()
        self._overlay_items.clear()
        self._pixmap_item = None
        self._doc_path = None
        self._doc_bytes_hash = None


__all__ = ["PdfGraphicsView"]
