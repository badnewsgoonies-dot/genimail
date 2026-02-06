import os
import subprocess
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from genimail.constants import TAKEOFF_DEFAULT_COATS
from genimail.domain.quotes import build_quote_context
from genimail.infra.document_store import create_quote_doc, open_document_file
from genimail.paths import DEFAULT_QUOTE_TEMPLATE_FILE, QUOTE_DIR, ROOT_DIR
from genimail_qt.takeoff_engine import compute_takeoff, estimate_door_count, parse_length_to_feet


class DocsMixin:
    def _build_docs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        quote_group = QGroupBox("Quote Builder")
        quote_layout = QFormLayout(quote_group)
        self.quote_template_input = QLineEdit(self.config.get("quote_template_path", DEFAULT_QUOTE_TEMPLATE_FILE))
        self.quote_output_input = QLineEdit(self.config.get("quote_output_dir", QUOTE_DIR))
        self.quote_client_input = QLineEdit("")
        self.quote_email_input = QLineEdit("")
        self.quote_project_input = QLineEdit("")
        self.quote_reference_input = QLineEdit("")
        quote_layout.addRow("Template File", self.quote_template_input)
        quote_layout.addRow("Output Folder", self.quote_output_input)
        quote_layout.addRow("Client Name", self.quote_client_input)
        quote_layout.addRow("Client Email", self.quote_email_input)
        quote_layout.addRow("Project Name", self.quote_project_input)
        quote_layout.addRow("Reference", self.quote_reference_input)
        layout.addWidget(quote_group)

        quote_actions = QHBoxLayout()
        browse_template_btn = QPushButton("Browse Template")
        browse_output_btn = QPushButton("Browse Output")
        create_quote_btn = QPushButton("Create Quote Doc")
        create_quote_btn.setObjectName("primaryButton")
        open_output_btn = QPushButton("Open Quotes Folder")
        quote_actions.addWidget(browse_template_btn)
        quote_actions.addWidget(browse_output_btn)
        quote_actions.addWidget(create_quote_btn)
        quote_actions.addWidget(open_output_btn)
        quote_actions.addStretch(1)
        layout.addLayout(quote_actions)

        takeoff_group = QGroupBox("Takeoff (Beta)")
        takeoff_layout = QFormLayout(takeoff_group)
        default_wall_height = self.config.get("takeoff_default_wall_height", "8ft")
        self.takeoff_linear_input = QLineEdit("")
        self.takeoff_height_input = QLineEdit(str(default_wall_height))
        self.takeoff_door_count_input = QLineEdit("0")
        self.takeoff_window_area_input = QLineEdit("0")
        self.takeoff_coats_input = QLineEdit(str(TAKEOFF_DEFAULT_COATS))
        takeoff_layout.addRow("Linear Feet", self.takeoff_linear_input)
        takeoff_layout.addRow("Wall Height", self.takeoff_height_input)
        takeoff_layout.addRow("Door Count", self.takeoff_door_count_input)
        takeoff_layout.addRow("Window Area (sq ft)", self.takeoff_window_area_input)
        takeoff_layout.addRow("Coats", self.takeoff_coats_input)
        layout.addWidget(takeoff_group)

        takeoff_actions = QHBoxLayout()
        estimate_doors_btn = QPushButton("Estimate Doors")
        compute_takeoff_btn = QPushButton("Compute Area")
        compute_takeoff_btn.setObjectName("primaryButton")
        open_measure_tool_btn = QPushButton("Open Click-to-Measure Tool")
        takeoff_actions.addWidget(estimate_doors_btn)
        takeoff_actions.addWidget(compute_takeoff_btn)
        takeoff_actions.addWidget(open_measure_tool_btn)
        takeoff_actions.addStretch(1)
        layout.addLayout(takeoff_actions)

        self.takeoff_result_label = QLabel("Takeoff result will appear here.")
        self.takeoff_result_label.setWordWrap(True)
        layout.addWidget(self.takeoff_result_label)

        invoice_group = QGroupBox("Invoice Builder")
        invoice_layout = QVBoxLayout(invoice_group)
        invoice_layout.addWidget(
            QLabel(
                "Invoice builder is reserved for the next phase.\n"
                "The workspace structure is ready for direct integration."
            )
        )
        layout.addWidget(invoice_group)
        layout.addStretch(1)

        browse_template_btn.clicked.connect(self._browse_quote_template)
        browse_output_btn.clicked.connect(self._browse_quote_output)
        create_quote_btn.clicked.connect(self._create_quote_document)
        open_output_btn.clicked.connect(self._open_quote_output_folder)
        estimate_doors_btn.clicked.connect(self._estimate_takeoff_doors)
        compute_takeoff_btn.clicked.connect(self._compute_takeoff_area)
        open_measure_tool_btn.clicked.connect(self._open_takeoff_tool)
        return tab

    def _browse_quote_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Quote Template",
            self.quote_template_input.text().strip() or DEFAULT_QUOTE_TEMPLATE_FILE,
            "Word/Text Templates (*.doc *.docx *.txt);;All Files (*.*)",
        )
        if not path:
            return
        self.quote_template_input.setText(path)
        self.config.set("quote_template_path", path)

    def _browse_quote_output(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Quote Output Folder",
            self.quote_output_input.text().strip() or QUOTE_DIR,
        )
        if not path:
            return
        self.quote_output_input.setText(path)
        self.config.set("quote_output_dir", path)

    def _create_quote_document(self):
        template_path = self.quote_template_input.text().strip() or DEFAULT_QUOTE_TEMPLATE_FILE
        output_dir = self.quote_output_input.text().strip() or QUOTE_DIR
        context = build_quote_context(
            to_value=self.quote_email_input.text().strip(),
            subject_value=self.quote_project_input.text().strip(),
        )
        if self.quote_client_input.text().strip():
            context["client_name"] = self.quote_client_input.text().strip()
        if self.quote_reference_input.text().strip():
            context["email_subject"] = self.quote_reference_input.text().strip()
        try:
            quote_path = create_quote_doc(template_path, output_dir, context)
        except Exception as exc:
            QMessageBox.critical(self, "Quote Error", str(exc))
            return

        self._set_status(f"Quote created: {os.path.basename(quote_path)}")
        opened = open_document_file(quote_path)
        if not opened:
            QMessageBox.information(self, "Quote Created", f"Quote created at:\n{quote_path}")

    def _open_quote_output_folder(self):
        folder = self.quote_output_input.text().strip() or QUOTE_DIR
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _estimate_takeoff_doors(self):
        linear_raw = self.takeoff_linear_input.text().strip()
        if not linear_raw:
            QMessageBox.information(self, "Linear Feet Needed", "Enter linear feet before estimating doors.")
            return
        try:
            linear_feet = parse_length_to_feet(linear_raw, default_unit="ft")
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Linear Feet", str(exc))
            return
        estimate = estimate_door_count(linear_feet)
        self.takeoff_door_count_input.setText(str(estimate))
        self._set_status(f"Door estimate set to {estimate}")

    def _compute_takeoff_area(self):
        linear_raw = self.takeoff_linear_input.text().strip()
        height_raw = self.takeoff_height_input.text().strip()
        door_count_raw = self.takeoff_door_count_input.text().strip() or "0"
        window_area_raw = self.takeoff_window_area_input.text().strip() or "0"
        coats_raw = self.takeoff_coats_input.text().strip() or str(TAKEOFF_DEFAULT_COATS)

        if not linear_raw or not height_raw:
            QMessageBox.information(self, "Missing Inputs", "Provide linear feet and wall height.")
            return

        try:
            linear_feet = parse_length_to_feet(linear_raw, default_unit="ft")
            wall_height = parse_length_to_feet(height_raw, default_unit="ft")
            door_count = int(door_count_raw)
            window_area_sqft = float(window_area_raw)
            coats = int(coats_raw)
            result = compute_takeoff(
                linear_feet=linear_feet,
                wall_height_feet=wall_height,
                door_count=door_count,
                window_area_sqft=window_area_sqft,
                coats=coats,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Takeoff Error", str(exc))
            return

        self.config.set("takeoff_default_wall_height", height_raw)
        self.takeoff_result_label.setText(
            f"Gross: {result.gross_area_sqft:.1f} sq ft · "
            f"Openings: {result.opening_area_sqft:.1f} sq ft · "
            f"Net: {result.net_area_sqft:.1f} sq ft · "
            f"Paint Area ({result.coats} coat(s)): {result.paint_area_sqft:.1f} sq ft"
        )
        self._set_status("Takeoff area computed")

    def _open_takeoff_tool(self):
        takeoff_script = os.path.join(ROOT_DIR, "pdf_takeoff_tool.py")
        if not os.path.isfile(takeoff_script):
            QMessageBox.warning(self, "Takeoff Tool Missing", f"Could not find takeoff tool:\n{takeoff_script}")
            return
        try:
            subprocess.Popen([sys.executable, takeoff_script], cwd=ROOT_DIR)
            self._set_status("Takeoff tool opened")
        except Exception as exc:
            QMessageBox.critical(self, "Takeoff Launch Failed", str(exc))

    def _launch_scanner(self):
        scanner_script = os.path.join(ROOT_DIR, "scanner_app_v4.py")
        if not os.path.isfile(scanner_script):
            QMessageBox.warning(self, "Scanner Missing", f"Could not find scanner script:\n{scanner_script}")
            return
        try:
            subprocess.Popen([sys.executable, scanner_script], cwd=ROOT_DIR)
            self._set_status("Scanner opened")
        except Exception as exc:
            QMessageBox.critical(self, "Scanner Launch Failed", str(exc))


__all__ = ["DocsMixin"]
