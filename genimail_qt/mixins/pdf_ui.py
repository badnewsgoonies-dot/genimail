from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QLineEdit,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from genimail.constants import TAKEOFF_DEFAULT_WALL_HEIGHT

TOOL_PANEL_WIDTH = 180


class PdfUiMixin:
    def _build_pdf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar row ──────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        open_btn = QPushButton("Open PDF")
        close_btn = QPushButton("Close Tab")
        toolbar.addWidget(open_btn)
        toolbar.addWidget(close_btn)
        toolbar.addStretch(1)

        self._pdf_prev_btn = QPushButton("\u25C0")
        self._pdf_prev_btn.setFixedWidth(32)
        self._pdf_page_label = QLabel("Page 0/0")
        self._pdf_next_btn = QPushButton("\u25B6")
        self._pdf_next_btn.setFixedWidth(32)
        toolbar.addWidget(self._pdf_prev_btn)
        toolbar.addWidget(self._pdf_page_label)
        toolbar.addWidget(self._pdf_next_btn)
        toolbar.addStretch(1)

        fit_btn = QPushButton("Fit")
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(32)
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedWidth(32)
        toolbar.addWidget(fit_btn)
        toolbar.addWidget(zoom_in_btn)
        toolbar.addWidget(zoom_out_btn)

        layout.addLayout(toolbar)

        # ── Splitter: tool panel | pdf tabs ──────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: tool panel
        tool_panel = QWidget()
        tool_panel.setObjectName("pdfToolPanel")
        tool_panel.setFixedWidth(TOOL_PANEL_WIDTH)
        tp_layout = QVBoxLayout(tool_panel)
        tp_layout.setContentsMargins(8, 8, 8, 8)
        tp_layout.setSpacing(6)

        # Tool mode radio buttons
        tp_layout.addWidget(QLabel("Tool:"))
        self._pdf_tool_navigate = QRadioButton("Navigate")
        self._pdf_tool_calibrate = QRadioButton("Calibrate")
        self._pdf_tool_floorplan = QRadioButton("Floor Plan")
        self._pdf_tool_navigate.setChecked(True)
        self._pdf_tool_group = QButtonGroup(tool_panel)
        self._pdf_tool_group.addButton(self._pdf_tool_navigate, 0)
        self._pdf_tool_group.addButton(self._pdf_tool_calibrate, 1)
        self._pdf_tool_group.addButton(self._pdf_tool_floorplan, 2)
        tp_layout.addWidget(self._pdf_tool_navigate)
        tp_layout.addWidget(self._pdf_tool_calibrate)
        tp_layout.addWidget(self._pdf_tool_floorplan)

        # Separator
        sep1 = QLabel("")
        sep1.setFixedHeight(1)
        sep1.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep1)

        # Calibration section
        tp_layout.addWidget(QLabel("Calibration:"))
        self._pdf_cal_status = QLabel("Not calibrated")
        self._pdf_cal_status.setObjectName("pdfCalStatus")
        self._pdf_cal_status.setWordWrap(True)
        tp_layout.addWidget(self._pdf_cal_status)

        # Separator
        sep2 = QLabel("")
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep2)

        # Wall height
        tp_layout.addWidget(QLabel("Wall Height:"))
        default_wall_ht = TAKEOFF_DEFAULT_WALL_HEIGHT
        if hasattr(self, "config"):
            default_wall_ht = self.config.get("takeoff_default_wall_height", TAKEOFF_DEFAULT_WALL_HEIGHT)
        self._pdf_wall_height_input = QLineEdit(str(default_wall_ht))
        self._pdf_wall_height_input.setPlaceholderText("e.g. 8ft")
        tp_layout.addWidget(self._pdf_wall_height_input)

        # Current shape section
        sep3 = QLabel("")
        sep3.setFixedHeight(1)
        sep3.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep3)
        tp_layout.addWidget(QLabel("Current Shape:"))

        self._pdf_points_label = QLabel("Points: 0")
        self._pdf_points_label.setObjectName("pdfResultLabel")
        tp_layout.addWidget(self._pdf_points_label)

        self._pdf_close_shape_btn = QPushButton("Close Shape")
        self._pdf_close_wall_btn = QPushButton("Close Wall")
        self._pdf_undo_btn = QPushButton("Undo Point")
        self._pdf_clear_btn = QPushButton("Clear")
        tp_layout.addWidget(self._pdf_close_shape_btn)
        tp_layout.addWidget(self._pdf_close_wall_btn)
        tp_layout.addWidget(self._pdf_undo_btn)
        tp_layout.addWidget(self._pdf_clear_btn)

        # Rooms list
        sep4 = QLabel("")
        sep4.setFixedHeight(1)
        sep4.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep4)
        tp_layout.addWidget(QLabel("Rooms:"))

        self._pdf_rooms_list = QListWidget()
        self._pdf_rooms_list.setObjectName("pdfRoomsList")
        self._pdf_rooms_list.setMaximumHeight(160)
        self._pdf_rooms_list.setAlternatingRowColors(True)
        tp_layout.addWidget(self._pdf_rooms_list)

        # Totals
        sep5 = QLabel("")
        sep5.setFixedHeight(1)
        sep5.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep5)
        tp_layout.addWidget(QLabel("Totals:"))

        self._pdf_total_perim_label = QLabel("Perimeter: \u2014")
        self._pdf_total_wall_label = QLabel("Wall Sqft: \u2014")
        self._pdf_total_floor_label = QLabel("Floor Sqft: \u2014")
        for lbl in (self._pdf_total_perim_label, self._pdf_total_wall_label,
                     self._pdf_total_floor_label):
            lbl.setObjectName("pdfResultLabel")
            tp_layout.addWidget(lbl)

        # Room management buttons
        sep6 = QLabel("")
        sep6.setFixedHeight(1)
        sep6.setStyleSheet("background: #dfe3ea;")
        tp_layout.addWidget(sep6)

        self._pdf_remove_room_btn = QPushButton("Remove Selected")
        self._pdf_clear_all_btn = QPushButton("Clear All")
        self._pdf_copy_totals_btn = QPushButton("Copy Totals")
        tp_layout.addWidget(self._pdf_remove_room_btn)
        tp_layout.addWidget(self._pdf_clear_all_btn)
        tp_layout.addWidget(self._pdf_copy_totals_btn)

        tp_layout.addStretch(1)

        splitter.addWidget(tool_panel)

        # Right: pdf tab widget
        self.pdf_tabs = QTabWidget()
        self.pdf_tabs.setTabsClosable(True)
        self.pdf_tabs.tabCloseRequested.connect(self._on_pdf_tab_close_requested)
        splitter.addWidget(self.pdf_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # ── Wire toolbar buttons ─────────────────────────────────
        open_btn.clicked.connect(self._open_pdf_dialog)
        close_btn.clicked.connect(self._close_current_pdf_tab)
        self._pdf_prev_btn.clicked.connect(self._on_pdf_prev_page)
        self._pdf_next_btn.clicked.connect(self._on_pdf_next_page)
        fit_btn.clicked.connect(self._on_pdf_fit_width)
        zoom_in_btn.clicked.connect(self._on_pdf_zoom_in)
        zoom_out_btn.clicked.connect(self._on_pdf_zoom_out)

        self._pdf_close_shape_btn.clicked.connect(self._on_pdf_close_shape)
        self._pdf_close_wall_btn.clicked.connect(self._on_pdf_close_wall)
        self._pdf_undo_btn.clicked.connect(self._on_pdf_undo_point)
        self._pdf_clear_btn.clicked.connect(self._on_pdf_clear_polygon)
        self._pdf_remove_room_btn.clicked.connect(self._on_pdf_remove_room)
        self._pdf_clear_all_btn.clicked.connect(self._on_pdf_clear_all_rooms)
        self._pdf_copy_totals_btn.clicked.connect(self._on_pdf_copy_totals)

        self._pdf_tool_group.idToggled.connect(self._on_pdf_tool_changed)

        self._add_pdf_placeholder_tab()
        return tab


__all__ = ["PdfUiMixin"]
