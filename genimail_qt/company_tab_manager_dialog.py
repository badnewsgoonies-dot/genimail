from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


def normalize_company_query(value):
    query = (value or "").strip().lower()
    if not query:
        return ""
    if query.startswith("@"):
        return query[1:].strip()
    return query


class CompanyTabManagerDialog(QDialog):
    def __init__(self, parent, tabs):
        super().__init__(parent)
        self.setWindowTitle("Manage Company Tabs")
        self.resize(520, 420)

        self.changed = False
        self.tabs = [normalize_company_query(item) for item in (tabs or []) if normalize_company_query(item)]

        root = QVBoxLayout(self)
        intro = QLabel(
            "Manage company tabs used for cross-folder retrieval.\n"
            "Matching rules: full email = exact sender, domain = exact sender domain, text = contains."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.tab_list = QListWidget()
        self.tab_list.currentRowChanged.connect(lambda _row: self._update_action_states())
        root.addWidget(self.tab_list, 1)

        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.remove_btn = QPushButton("Remove")
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("primaryButton")
        actions.addWidget(self.add_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self.add_btn.clicked.connect(self._add_tab)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.close_btn.clicked.connect(self.accept)

        self._refresh_list()

    def _refresh_list(self):
        self.tab_list.clear()
        for tab in self.tabs:
            self.tab_list.addItem(tab)
        if self.tab_list.count() > 0:
            self.tab_list.setCurrentRow(0)
        self._update_action_states()

    def _update_action_states(self):
        has_selection = self.tab_list.currentRow() >= 0
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

    def _prompt_query(self, title, text=""):
        value, ok = QInputDialog.getText(self, title, "Company query:", text=text)
        if not ok:
            return None
        normalized = normalize_company_query(value)
        if not normalized:
            QMessageBox.information(self, "Invalid Query", "Company query cannot be empty.")
            return None
        return normalized

    def _add_tab(self):
        query = self._prompt_query("Add Company Tab")
        if query is None:
            return
        if query in self.tabs:
            QMessageBox.information(self, "Duplicate", "That company tab already exists.")
            return
        self.tabs.append(query)
        self.changed = True
        self._refresh_list()

    def _edit_selected(self):
        row = self.tab_list.currentRow()
        if row < 0 or row >= len(self.tabs):
            return
        current = self.tabs[row]
        query = self._prompt_query("Edit Company Tab", current)
        if query is None:
            return
        if query != current and query in self.tabs:
            QMessageBox.information(self, "Duplicate", "That company tab already exists.")
            return
        self.tabs[row] = query
        self.changed = True
        self._refresh_list()
        self.tab_list.setCurrentRow(row)

    def _remove_selected(self):
        row = self.tab_list.currentRow()
        if row < 0 or row >= len(self.tabs):
            return
        removed = self.tabs.pop(row)
        self.changed = True
        self._refresh_list()
        QMessageBox.information(self, "Removed", f'Removed "{removed}"')


__all__ = ["CompanyTabManagerDialog", "normalize_company_query"]
