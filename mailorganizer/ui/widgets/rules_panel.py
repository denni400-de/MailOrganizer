"""Tab 3: Analyse-Regeln — CRUD UI for the conditional rules engine (plan section 8.1)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.config import constants
from mailorganizer.services.rules_service import RuleCondition
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import MailOrganizerError


class RuleEditDialog(QDialog):
    """Add/edit dialog for a single analysis rule: one field/operator/value clause + action."""

    def __init__(self, parent=None, rule=None):
        super().__init__(parent)
        self.setWindowTitle("Regel bearbeiten" if rule else "Neue Regel")
        self.rule = rule

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.field_combo = QComboBox()
        self.field_combo.addItems(constants.RULE_FIELDS)
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(constants.RULE_OPERATORS)
        self.value_edit = QLineEdit()
        self.action_combo = QComboBox()
        self.action_combo.addItems(constants.RULE_ACTIONS)
        self.action_combo.currentTextChanged.connect(self._on_action_changed)
        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("z.B. shopping")
        self.category_label = QLabel("Ziel-Kategorie:")
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        self.priority_spin.setValue(1)
        self.active_check = QCheckBox("Aktiv")
        self.active_check.setChecked(True)

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Feld:", self.field_combo)
        layout.addRow("Operator:", self.operator_combo)
        layout.addRow("Wert:", self.value_edit)
        layout.addRow("Aktion:", self.action_combo)
        layout.addRow(self.category_label, self.category_edit)
        layout.addRow("Priorität:", self.priority_spin)
        layout.addRow(self.active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_action_changed(self.action_combo.currentText())

        if rule is not None:
            self._load_rule(rule)

    def _on_action_changed(self, action: str) -> None:
        show = action == "category"
        self.category_label.setVisible(show)
        self.category_edit.setVisible(show)

    def _load_rule(self, rule) -> None:
        self.name_edit.setText(rule.name)
        try:
            condition = RuleCondition.from_json(rule.condition)
            self.field_combo.setCurrentText(condition.field)
            self.operator_combo.setCurrentText(condition.operator)
            self.value_edit.setText(str(condition.value))
            if condition.set_category:
                self.category_edit.setText(condition.set_category)
        except MailOrganizerError:
            pass
        self.action_combo.setCurrentText(rule.action)
        self.priority_spin.setValue(rule.priority)
        self.active_check.setChecked(rule.is_active)

    def result_values(self) -> dict:
        condition = RuleCondition(
            field=self.field_combo.currentText(),
            operator=self.operator_combo.currentText(),
            value=self.value_edit.text().strip(),
            set_category=self.category_edit.text().strip() or None,
        )
        return {
            "name": self.name_edit.text().strip(),
            "condition": condition.to_json(),
            "action": self.action_combo.currentText(),
            "priority": self.priority_spin.value(),
            "is_active": self.active_check.isChecked(),
        }


class AnalysisRulesTab(QWidget):
    """Tab 3: table of analysis rules with add/edit/delete controls."""

    def __init__(self, storage: StorageService, user_id: int | None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Bedingung", "Aktion", "Priorität", "Aktiv"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Hinzufügen")
        self.edit_button = QPushButton("Bearbeiten")
        self.delete_button = QPushButton("Löschen")
        for btn in (self.add_button, self.edit_button, self.delete_button):
            button_row.addWidget(btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.add_button.clicked.connect(self._add_rule)
        self.edit_button.clicked.connect(self._edit_rule)
        self.delete_button.clicked.connect(self._delete_rule)

        self._rule_ids: list[int] = []

        if self.user_id is None:
            self.setEnabled(False)
        else:
            self.refresh()

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id
        self.setEnabled(True)
        self.refresh()

    def refresh(self) -> None:
        if self.user_id is None:
            return
        rules = self.storage.list_rules(self.user_id)
        self.table.setRowCount(0)
        self._rule_ids = []
        for rule in rules:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(rule.name))
            self.table.setItem(row, 1, QTableWidgetItem(rule.condition))
            self.table.setItem(row, 2, QTableWidgetItem(rule.action))
            self.table.setItem(row, 3, QTableWidgetItem(str(rule.priority)))
            self.table.setItem(row, 4, QTableWidgetItem("Ja" if rule.is_active else "Nein"))
            self._rule_ids.append(rule.id)

    def _selected_rule_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._rule_ids):
            return self._rule_ids[row]
        return None

    def _add_rule(self) -> None:
        if self.user_id is None:
            return
        dialog = RuleEditDialog(self)
        if dialog.exec():
            values = dialog.result_values()
            if not values["name"]:
                QMessageBox.warning(self, "Fehler", "Bitte einen Namen für die Regel angeben.")
                return
            self.storage.create_rule(self.user_id, **values)
            self.refresh()

    def _edit_rule(self) -> None:
        rule_id = self._selected_rule_id()
        if rule_id is None:
            return
        rule = next((r for r in self.storage.list_rules(self.user_id) if r.id == rule_id), None)
        if rule is None:
            return
        dialog = RuleEditDialog(self, rule=rule)
        if dialog.exec():
            values = dialog.result_values()
            self.storage.update_rule(rule_id, **values)
            self.refresh()

    def _delete_rule(self) -> None:
        rule_id = self._selected_rule_id()
        if rule_id is None:
            return
        if QMessageBox.question(self, "Regel löschen", "Diese Regel wirklich löschen?") == QMessageBox.StandardButton.Yes:
            self.storage.delete_rule(rule_id)
            self.refresh()
