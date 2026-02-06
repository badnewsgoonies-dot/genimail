from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from genimail.domain.helpers import normalize_company_query


class CompanyTabManagerDialog(QDialog):
    def __init__(self, parent, entries, all_domains=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Company Tabs")
        self.resize(620, 460)

        self.changed = False
        self.entries = []
        self._editing_row = None

        seen_domains = set()
        for item in entries or []:
            normalized = self._normalize_entry(item)
            if not normalized:
                continue
            domain = normalized["domain"]
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            self.entries.append(normalized)

        suggestions = []
        for item in all_domains or []:
            if isinstance(item, dict):
                domain = normalize_company_query(item.get("domain", ""))
            else:
                domain = normalize_company_query(item)
            if domain and domain not in suggestions:
                suggestions.append(domain)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Add company domains for cross-folder retrieval.\n"
            "Optional labels are shown on tabs and the active company badge."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        add_row = QHBoxLayout()
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("Domain (e.g., acme.com)")
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Display label (optional)")
        self.add_btn = QPushButton("Add")
        add_row.addWidget(self.domain_input, 3)
        add_row.addWidget(self.label_input, 3)
        add_row.addWidget(self.add_btn)
        root.addLayout(add_row)

        self._completer = QCompleter(suggestions, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.domain_input.setCompleter(self._completer)

        self.entry_list = QListWidget()
        self.entry_list.currentRowChanged.connect(lambda _row: self._update_action_states())
        root.addWidget(self.entry_list, 1)

        actions = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.remove_btn = QPushButton("Remove")
        self.move_up_btn = QPushButton("Move Up")
        self.move_down_btn = QPushButton("Move Down")
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("primaryButton")
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.remove_btn)
        actions.addWidget(self.move_up_btn)
        actions.addWidget(self.move_down_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.add_btn.clicked.connect(self._add_or_update_entry)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.move_up_btn.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_btn.clicked.connect(lambda: self._move_selected(1))
        self.close_btn.clicked.connect(self.accept)
        self.domain_input.returnPressed.connect(self._add_or_update_entry)
        self.label_input.returnPressed.connect(self._add_or_update_entry)

        self._refresh_list()

    @staticmethod
    def _normalize_entry(item):
        if isinstance(item, str):
            domain = normalize_company_query(item)
            if not domain:
                return None
            return {"domain": domain, "label": ""}
        if isinstance(item, dict):
            domain = normalize_company_query(item.get("domain", ""))
            if not domain:
                return None
            return {"domain": domain, "label": (item.get("label") or "").strip()}
        return None

    @staticmethod
    def _format_entry_text(entry):
        domain = entry.get("domain", "")
        label = (entry.get("label") or "").strip()
        if label and label.lower() != domain:
            return f"{label} ({domain})"
        return domain

    def _refresh_list(self):
        current_row = self.entry_list.currentRow()
        self.entry_list.clear()
        for entry in self.entries:
            self.entry_list.addItem(self._format_entry_text(entry))
        if self.entry_list.count() > 0:
            if 0 <= current_row < self.entry_list.count():
                self.entry_list.setCurrentRow(current_row)
            else:
                self.entry_list.setCurrentRow(0)
        self._update_action_states()

    def _clear_editor(self):
        self._editing_row = None
        self.add_btn.setText("Add")
        self.domain_input.clear()
        self.label_input.clear()

    def _update_action_states(self):
        row = self.entry_list.currentRow()
        has_selection = row >= 0
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and row > 0)
        self.move_down_btn.setEnabled(has_selection and row < len(self.entries) - 1)

    def _add_or_update_entry(self):
        domain = normalize_company_query(self.domain_input.text())
        label = (self.label_input.text() or "").strip()
        if not domain:
            QMessageBox.information(self, "Invalid Domain", "Domain cannot be empty.")
            return
        if "." not in domain:
            QMessageBox.information(self, "Invalid Domain", "Domain must include a dot (for example, acme.com).")
            return

        edit_row = self._editing_row
        for idx, entry in enumerate(self.entries):
            if idx == edit_row:
                continue
            if entry.get("domain") == domain:
                QMessageBox.information(self, "Duplicate", "That company domain already exists.")
                return

        if edit_row is None:
            self.entries.append({"domain": domain, "label": label})
            selected_row = len(self.entries) - 1
        else:
            self.entries[edit_row] = {"domain": domain, "label": label}
            selected_row = edit_row

        self.changed = True
        self._clear_editor()
        self._refresh_list()
        if 0 <= selected_row < self.entry_list.count():
            self.entry_list.setCurrentRow(selected_row)
        self.domain_input.setFocus()

    def _edit_selected(self):
        row = self.entry_list.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        self._editing_row = row
        self.domain_input.setText(entry.get("domain", ""))
        self.label_input.setText(entry.get("label", ""))
        self.add_btn.setText("Save")
        self.domain_input.setFocus()
        self.domain_input.selectAll()

    def _remove_selected(self):
        row = self.entry_list.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        answer = QMessageBox.question(
            self,
            "Remove Company",
            f'Remove "{self._format_entry_text(entry)}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.entries.pop(row)
        self.changed = True
        self._clear_editor()
        self._refresh_list()
        if self.entry_list.count() > 0:
            self.entry_list.setCurrentRow(min(row, self.entry_list.count() - 1))

    def _move_selected(self, offset):
        row = self.entry_list.currentRow()
        if row < 0:
            return
        target = row + offset
        if target < 0 or target >= len(self.entries):
            return

        self.entries[row], self.entries[target] = self.entries[target], self.entries[row]
        self.changed = True
        self._refresh_list()
        self.entry_list.setCurrentRow(target)


__all__ = ["CompanyTabManagerDialog", "normalize_company_query"]
