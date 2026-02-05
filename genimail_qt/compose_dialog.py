import base64
import os

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from genimail.constants import APP_NAME
from genimail_qt.constants import COMPOSE_DIALOG_SIZE


class ComposeDialog(QDialog):
    def __init__(self, parent, mode_label, defaults, on_send):
        super().__init__(parent)
        self._on_send = on_send
        self._attachments = []
        self.setWindowTitle(f"{mode_label} - {APP_NAME}")
        self.resize(*COMPOSE_DIALOG_SIZE)

        root_layout = QVBoxLayout(self)

        form = QFormLayout()
        self.to_input = QLineEdit(defaults.get("to", ""))
        self.cc_input = QLineEdit(defaults.get("cc", ""))
        self.subject_input = QLineEdit(defaults.get("subject", ""))
        form.addRow("To", self.to_input)
        form.addRow("CC", self.cc_input)
        form.addRow("Subject", self.subject_input)
        root_layout.addLayout(form)

        self.body_input = QTextEdit(defaults.get("body", ""))
        self.body_input.setPlaceholderText("Write your message...")
        root_layout.addWidget(self.body_input, 1)

        attach_box = QGroupBox("Attachments")
        attach_layout = QVBoxLayout(attach_box)
        self.attach_list = QListWidget()
        attach_layout.addWidget(self.attach_list, 1)
        attach_row = QHBoxLayout()
        self.add_attach_btn = QPushButton("Add Files")
        self.remove_attach_btn = QPushButton("Remove Selected")
        attach_row.addWidget(self.add_attach_btn)
        attach_row.addWidget(self.remove_attach_btn)
        attach_row.addStretch(1)
        attach_layout.addLayout(attach_row)
        root_layout.addWidget(attach_box)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        bottom_row.addWidget(self.send_btn)
        bottom_row.addWidget(cancel_btn)
        root_layout.addLayout(bottom_row)

        self.add_attach_btn.clicked.connect(self._on_add_attachment)
        self.remove_attach_btn.clicked.connect(self._on_remove_attachment)
        self.send_btn.clicked.connect(self._on_send_clicked)
        cancel_btn.clicked.connect(self.reject)

    def _on_add_attachment(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if not files:
            return
        for path in files:
            normalized = os.path.abspath(path)
            if normalized in self._attachments:
                continue
            self._attachments.append(normalized)
            self.attach_list.addItem(normalized)

    def _on_remove_attachment(self):
        row = self.attach_list.currentRow()
        if row < 0:
            return
        self.attach_list.takeItem(row)
        self._attachments.pop(row)

    def _on_send_clicked(self):
        payload = self._collect_payload()
        if payload is None:
            return
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending...")
        self._on_send(payload, self)

    def _collect_payload(self):
        to_list = [item.strip() for item in self.to_input.text().split(";") if item.strip()]
        if not to_list:
            QMessageBox.warning(self, "Missing Recipient", "Add at least one recipient in To.")
            return None

        cc_list = [item.strip() for item in self.cc_input.text().split(";") if item.strip()]
        subject = self.subject_input.text().strip()
        body = self.body_input.toPlainText()

        attachments = []
        for path in self._attachments:
            try:
                with open(path, "rb") as handle:
                    encoded = base64.b64encode(handle.read()).decode("utf-8")
                attachments.append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(path),
                        "contentBytes": encoded,
                    }
                )
            except OSError as exc:
                QMessageBox.warning(self, "Attachment Error", f"Could not read attachment:\n{path}\n\n{exc}")
                return None

        return {
            "to": to_list,
            "cc": cc_list,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        }

    def mark_send_failed(self, message):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        QMessageBox.critical(self, "Send Failed", message)


__all__ = ["ComposeDialog"]
