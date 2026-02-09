import math
import os
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QLabel, QMessageBox

from genimail.infra.document_store import open_document_file
from genimail.paths import PDF_DIR
from genimail_qt.pdf_graphics_view import PdfGraphicsView
from genimail_qt.takeoff_engine import compute_floor_plan, parse_length_to_feet
from genimail_qt.webview_page import FilteredWebEnginePage

# Tool mode IDs (match QButtonGroup ids in pdf_ui.py)
_TOOL_NAVIGATE = 0
_TOOL_CALIBRATE = 1
_TOOL_FLOORPLAN = 2


@dataclass
class SavedRoom:
    points_count: int
    perimeter_feet: float
    wall_sqft: float
    floor_sqft: float
    points: list = field(default_factory=list)
    page_index: int = 0


class PdfMixin:
    # ── Measurement state (per-session, cleared on page/doc change) ──
    _poly_points = None  # [(x_pt, y_pt), ...]
    _cal_factor = 1.0
    _has_cal = False
    _cal_start = None  # (x_pt, y_pt) for calibrate first click

    def _init_pdf_measurement_state(self):
        self._poly_points = []
        self._saved_rooms = []
        self._cal_factor = 1.0
        self._has_cal = False
        self._cal_start = None

    # ── Open / create ────────────────────────────────────────────

    def _open_pdf_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", PDF_DIR, "PDF Files (*.pdf);;All Files (*.*)")
        if not path:
            return
        self._open_pdf_file(path, activate=True)

    def _open_pdf_file(self, path, activate=False):
        normalized = os.path.abspath(path)
        if not os.path.isfile(normalized):
            QMessageBox.warning(self, "PDF Not Found", f"Could not find PDF:\n{normalized}")
            return
        existing_index = self._find_pdf_tab_index(normalized)
        if existing_index is not None:
            self.pdf_tabs.setCurrentIndex(existing_index)
            if activate:
                self.workspace_tabs.setCurrentWidget(self.pdf_tab)
            return

        for idx in reversed(range(self.pdf_tabs.count())):
            widget = self.pdf_tabs.widget(idx)
            if widget is not None and widget.property("is_placeholder"):
                self.pdf_tabs.removeTab(idx)
                widget.deleteLater()

        try:
            view = self._create_pdf_widget(normalized)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Load Error", f"Could not open PDF:\n{normalized}\n\n{exc}")
            return

        view.setProperty("pdf_path", normalized.lower())
        tab_label = os.path.basename(normalized)
        self.pdf_tabs.addTab(view, tab_label)
        self.pdf_tabs.setCurrentWidget(view)
        if activate:
            self.workspace_tabs.setCurrentWidget(self.pdf_tab)
        self._set_status(f"Opened PDF: {tab_label}")

        self._on_pdf_doc_opened(view)

    def _create_pdf_widget(self, normalized_path):
        view = PdfGraphicsView()
        view.open_document(normalized_path)
        view.pointClicked.connect(self._on_pdf_point_clicked)
        view.pageChanged.connect(self._on_pdf_page_changed)
        return view

    # ── Tab management ───────────────────────────────────────────

    def _find_pdf_tab_index(self, path):
        normalized = path.lower()
        for idx in range(self.pdf_tabs.count()):
            widget = self.pdf_tabs.widget(idx)
            if widget is None:
                continue
            if widget.property("pdf_path") == normalized:
                return idx
        return None

    def _on_pdf_tab_close_requested(self, index):
        widget = self.pdf_tabs.widget(index)
        if widget is not None:
            if isinstance(widget, PdfGraphicsView):
                widget.close_document()
            self.pdf_tabs.removeTab(index)
            widget.deleteLater()
        if self.pdf_tabs.count() == 0:
            self._add_pdf_placeholder_tab()
            self._update_pdf_page_label(0, 0)

    def _close_current_pdf_tab(self):
        idx = self.pdf_tabs.currentIndex()
        if idx >= 0:
            self._on_pdf_tab_close_requested(idx)

    def _add_pdf_placeholder_tab(self):
        placeholder = QLabel("Open a PDF to view it here.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setProperty("is_placeholder", True)
        self.pdf_tabs.addTab(placeholder, "Current PDF")

    # ── Current view helper ──────────────────────────────────────

    def _current_pdf_view(self):
        widget = self.pdf_tabs.currentWidget()
        if isinstance(widget, PdfGraphicsView):
            return widget
        return None

    # ── Page navigation ──────────────────────────────────────────

    def _on_pdf_prev_page(self):
        view = self._current_pdf_view()
        if view:
            view.prev_page()

    def _on_pdf_next_page(self):
        view = self._current_pdf_view()
        if view:
            view.next_page()

    def _on_pdf_page_changed(self, current, total):
        self._update_pdf_page_label(current, total)
        self._clear_polygon()
        self._redraw_all_room_overlays()

    def _update_pdf_page_label(self, current, total):
        if hasattr(self, "_pdf_page_label"):
            self._pdf_page_label.setText(f"Page {current + 1}/{total}" if total > 0 else "Page 0/0")

    # ── Zoom ─────────────────────────────────────────────────────

    def _on_pdf_fit_width(self):
        view = self._current_pdf_view()
        if view:
            view.fit_width()

    def _on_pdf_zoom_in(self):
        view = self._current_pdf_view()
        if view:
            view.zoom_in()

    def _on_pdf_zoom_out(self):
        view = self._current_pdf_view()
        if view:
            view.zoom_out()

    # ── Tool mode switching ──────────────────────────────────────

    def _on_pdf_tool_changed(self, tool_id, checked):
        if not checked:
            return
        view = self._current_pdf_view()
        click_enabled = tool_id in (_TOOL_CALIBRATE, _TOOL_FLOORPLAN)
        if view:
            view.set_click_enabled(click_enabled)
        if tool_id == _TOOL_CALIBRATE:
            self._cal_start = None
            self._pdf_cal_status.setText(
                f"Cal: x{self._cal_factor:.4f}" if self._has_cal else "Click two points on a known dimension"
            )
        elif tool_id == _TOOL_FLOORPLAN:
            if not self._has_cal:
                self._pdf_cal_status.setText("Warning: not calibrated")

    # ── Document opened ──────────────────────────────────────────

    def _on_pdf_doc_opened(self, view):
        self._init_pdf_measurement_state()
        self._load_calibration(view.doc_key)
        total = view.page_count
        self._update_pdf_page_label(0, total)
        self._update_measurement_labels()
        self._rebuild_rooms_list()
        self._update_totals()
        # Ensure tool mode click state matches current radio
        tool_id = self._pdf_tool_group.checkedId()
        click_enabled = tool_id in (_TOOL_CALIBRATE, _TOOL_FLOORPLAN)
        view.set_click_enabled(click_enabled)

    # ── Point click routing ──────────────────────────────────────

    def _on_pdf_point_clicked(self, x_pt, y_pt):
        tool_id = self._pdf_tool_group.checkedId()
        if tool_id == _TOOL_CALIBRATE:
            self._on_cal_click(x_pt, y_pt)
        elif tool_id == _TOOL_FLOORPLAN:
            self._on_poly_click(x_pt, y_pt)

    # ── Calibration ──────────────────────────────────────────────

    def _on_cal_click(self, x_pt, y_pt):
        view = self._current_pdf_view()
        if not view:
            return
        if self._cal_start is None:
            self._cal_start = (x_pt, y_pt)
            view.clear_overlays()
            view.add_vertex_dot(x_pt, y_pt)
            self._pdf_cal_status.setText("Click second point...")
        else:
            x0, y0 = self._cal_start
            view.add_vertex_dot(x_pt, y_pt)
            view.add_edge_line(x0, y0, x_pt, y_pt)

            pdf_dist_pts = math.hypot(x_pt - x0, y_pt - y0)
            if pdf_dist_pts < 0.5:
                self._pdf_cal_status.setText("Points too close. Try again.")
                self._cal_start = None
                return

            text, ok = QInputDialog.getText(
                self, "Calibrate", "Enter the real-world length of this line\n(e.g. 10ft, 120in, 3m):"
            )
            if ok and text.strip():
                try:
                    real_feet = parse_length_to_feet(text.strip())
                    real_inches = real_feet * 12.0
                    pdf_inches = pdf_dist_pts / 72.0
                    self._cal_factor = real_inches / pdf_inches
                    self._has_cal = True
                    self._pdf_cal_status.setText(f"Cal: x{self._cal_factor:.4f}")
                    self._save_calibration(view.doc_key, self._cal_factor)
                except Exception as exc:
                    self._pdf_cal_status.setText(f"Error: {exc}")
            else:
                self._pdf_cal_status.setText("Calibration cancelled.")

            self._cal_start = None
            view.clear_overlays()

    def _save_calibration(self, doc_key, cal_factor):
        if not doc_key or not hasattr(self, "config"):
            return
        cal_data = self.config.get("pdf_calibration", {}) or {}
        cal_data[doc_key] = {"cal_factor": float(cal_factor)}
        self.config.set("pdf_calibration", cal_data)

    def _load_calibration(self, doc_key):
        self._has_cal = False
        self._cal_factor = 1.0
        if not doc_key or not hasattr(self, "config"):
            return
        cal_data = self.config.get("pdf_calibration", {}) or {}
        entry = cal_data.get(doc_key)
        if not entry:
            self._pdf_cal_status.setText("Not calibrated")
            return
        try:
            if isinstance(entry, dict):
                cf = float(entry.get("cal_factor", 1.0))
            else:
                cf = float(entry)
            if math.isfinite(cf) and cf > 0:
                self._cal_factor = cf
                self._has_cal = True
        except Exception:
            pass
        if self._has_cal:
            self._pdf_cal_status.setText(f"Cal: x{self._cal_factor:.4f}")
        else:
            self._pdf_cal_status.setText("Not calibrated")

    # ── Polygon (Floor Plan) ─────────────────────────────────────

    def _on_poly_click(self, x_pt, y_pt):
        view = self._current_pdf_view()
        if not view:
            return
        if self._poly_points is None:
            self._poly_points = []
        self._poly_points.append((x_pt, y_pt))
        self._redraw_all_room_overlays()
        self._update_measurement_labels()

    def _on_pdf_close_shape(self):
        if not self._poly_points or len(self._poly_points) < 3:
            if hasattr(self, "toaster"):
                self.toaster.show("Need at least 3 points to close shape.", kind="error")
            return
        view = self._current_pdf_view()

        # Compute room measurements
        cal = self._cal_factor
        points_feet = [(x / 72.0 * cal / 12.0, y / 72.0 * cal / 12.0) for x, y in self._poly_points]
        result = compute_floor_plan(points_feet, scale_factor=1.0)

        wall_height = 8.0
        try:
            wall_height = parse_length_to_feet(self._pdf_wall_height_input.text())
        except Exception:
            pass

        wall_sqft = result.perimeter_feet * wall_height
        floor_sqft = result.floor_area_sqft

        # Save room
        room = SavedRoom(
            points_count=len(self._poly_points),
            perimeter_feet=result.perimeter_feet,
            wall_sqft=wall_sqft,
            floor_sqft=floor_sqft,
            points=list(self._poly_points),
            page_index=view.current_page if view else 0,
        )
        self._saved_rooms.append(room)

        # Reset current polygon for next room (overlays redrawn to show saved rooms)
        self._poly_points = []
        self._update_measurement_labels()
        self._redraw_all_room_overlays()
        self._rebuild_rooms_list()
        self._update_totals()

    def _on_pdf_undo_point(self):
        if not self._poly_points:
            return
        self._poly_points.pop()
        self._redraw_all_room_overlays()
        self._update_measurement_labels()

    def _on_pdf_clear_polygon(self):
        self._clear_polygon()

    def _clear_polygon(self):
        self._poly_points = []
        self._cal_start = None
        self._redraw_all_room_overlays()
        self._update_measurement_labels()

    def _update_measurement_labels(self):
        n = len(self._poly_points) if self._poly_points else 0
        self._pdf_points_label.setText(f"Points: {n}")

    # ── Room accumulation ─────────────────────────────────────────

    def _rebuild_rooms_list(self):
        self._pdf_rooms_list.clear()
        for i, room in enumerate(self._saved_rooms, 1):
            text = f"{i}. {room.perimeter_feet:.1f} lf | {room.wall_sqft:.0f} wall | {room.floor_sqft:.0f} floor"
            self._pdf_rooms_list.addItem(text)

    def _update_totals(self):
        if not self._saved_rooms:
            self._pdf_total_perim_label.setText("Perimeter: \u2014")
            self._pdf_total_wall_label.setText("Wall Sqft: \u2014")
            self._pdf_total_floor_label.setText("Floor Sqft: \u2014")
            return
        total_perim = sum(r.perimeter_feet for r in self._saved_rooms)
        total_wall = sum(r.wall_sqft for r in self._saved_rooms)
        total_floor = sum(r.floor_sqft for r in self._saved_rooms)
        self._pdf_total_perim_label.setText(f"Perimeter: {total_perim:.1f} ft")
        self._pdf_total_wall_label.setText(f"Wall Sqft: {total_wall:,.0f}")
        self._pdf_total_floor_label.setText(f"Floor Sqft: {total_floor:,.0f}")

    def _on_pdf_remove_room(self):
        row = self._pdf_rooms_list.currentRow()
        if row < 0 or row >= len(self._saved_rooms):
            return
        self._saved_rooms.pop(row)
        self._rebuild_rooms_list()
        self._update_totals()
        self._redraw_all_room_overlays()

    def _on_pdf_clear_all_rooms(self):
        self._saved_rooms.clear()
        self._poly_points = []
        view = self._current_pdf_view()
        if view:
            view.clear_overlays()
        self._rebuild_rooms_list()
        self._update_totals()
        self._update_measurement_labels()

    def _on_pdf_copy_totals(self):
        if not self._saved_rooms:
            return
        total_perim = sum(r.perimeter_feet for r in self._saved_rooms)
        total_wall = sum(r.wall_sqft for r in self._saved_rooms)
        total_floor = sum(r.floor_sqft for r in self._saved_rooms)
        lines = [f"Rooms: {len(self._saved_rooms)}"]
        for i, room in enumerate(self._saved_rooms, 1):
            lines.append(f"  {i}. {room.perimeter_feet:.1f} lf | {room.wall_sqft:.0f} wall sqft | {room.floor_sqft:.0f} floor sqft")
        lines.append("Totals:")
        lines.append(f"  Perimeter: {total_perim:.1f} ft")
        lines.append(f"  Wall Sqft: {total_wall:,.0f}")
        lines.append(f"  Floor Sqft: {total_floor:,.0f}")
        QApplication.clipboard().setText("\n".join(lines))
        if hasattr(self, "toaster"):
            self.toaster.show("Totals copied to clipboard", kind="success")

    def _redraw_all_room_overlays(self):
        view = self._current_pdf_view()
        if not view:
            return
        view.clear_overlays()
        current_page = view.current_page
        for room in self._saved_rooms:
            if room.page_index != current_page:
                continue
            pts = room.points
            for pt in pts:
                view.add_vertex_dot(pt[0], pt[1])
            for i in range(len(pts)):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % len(pts)]
                view.add_edge_line(x0, y0, x1, y1)
        # Also redraw current in-progress polygon
        if self._poly_points:
            for pt in self._poly_points:
                view.add_vertex_dot(pt[0], pt[1])
            for i in range(1, len(self._poly_points)):
                x0, y0 = self._poly_points[i - 1]
                x1, y1 = self._poly_points[i]
                view.add_edge_line(x0, y0, x1, y1)

    # ── WebEngine support (used by email preview and other mixins) ──

    def _create_web_view(self, surface_name):
        view = QWebEngineView()
        page = FilteredWebEnginePage(surface_name, view)
        view.setPage(page)
        self._web_page_sources[page] = surface_name
        self._bind_web_downloads(view)
        return view

    def _bind_web_downloads(self, view):
        profile = view.page().profile()
        profile_id = id(profile)
        if profile_id in self._download_profile_ids:
            return
        profile.downloadRequested.connect(self._on_web_download_requested)
        self._download_profile_ids.add(profile_id)

    def _on_web_download_requested(self, download):
        page = download.page()
        source = self._web_page_sources.get(page, "web")
        message_id = (self.current_message or {}).get("id") if source == "email" else None
        if message_id:
            download.setProperty("message_id", message_id)
        download.setProperty("download_source", source)

        os.makedirs(PDF_DIR, exist_ok=True)
        suggested_name = download.downloadFileName() or "download.bin"
        target_path = self._unique_output_path(PDF_DIR, suggested_name)
        download.setDownloadDirectory(os.path.dirname(target_path))
        download.setDownloadFileName(os.path.basename(target_path))
        download.stateChanged.connect(lambda state, dl=download: self._on_web_download_state_changed(dl, state))
        download.accept()
        self._set_status(f"Downloading {os.path.basename(target_path)}...")

    def _on_web_download_state_changed(self, download, state):
        if state != QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            return
        directory = download.downloadDirectory() or ""
        filename = download.downloadFileName() or ""
        path = os.path.join(directory, filename) if directory and filename else ""
        if path:
            self._set_status(f"Downloaded {os.path.basename(path)}")
            self.toaster.show(
                f"Download complete · {os.path.basename(path)}",
                kind="success",
                action=lambda p=path: (
                    self._open_pdf_file(p, activate=True)
                    if p.lower().endswith(".pdf")
                    else open_document_file(p)
                ),
            )
            if hasattr(self, "_add_download_result_button"):
                self._add_download_result_button(path)

    @staticmethod
    def _unique_output_path(directory, filename):
        if not directory:
            return filename
        name = os.path.basename(filename or "download.bin")
        candidate = os.path.join(directory, name)
        if not os.path.exists(candidate):
            return candidate
        base, ext = os.path.splitext(name)
        index = 1
        while True:
            candidate = os.path.join(directory, f"{base}-{index}{ext}")
            if not os.path.exists(candidate):
                return candidate
            index += 1


__all__ = ["PdfMixin"]
