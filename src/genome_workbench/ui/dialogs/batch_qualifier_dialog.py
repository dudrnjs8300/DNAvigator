"""Batch qualifier edit dialog: apply one Set/Add/Remove qualifier operation
to every feature the user selected in the Feature Table at once.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

_COMMON_KEYS = ["gene", "locus_tag", "product", "note", "db_xref", "inference", "transl_table"]


class BatchQualifierDialog(QDialog):
    def __init__(self, feature_count: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch Edit Qualifiers")

        self._operation_combo = QComboBox()
        self._operation_combo.addItems(["Set (replace)", "Add (keep existing values)", "Remove"])
        self._operation_combo.currentIndexChanged.connect(self._on_operation_changed)

        self._key_combo = QComboBox()
        self._key_combo.setEditable(True)
        self._key_combo.addItems(_COMMON_KEYS)

        self._value_edit = QLineEdit()

        form = QFormLayout()
        form.addRow(QLabel(f"Applies to {feature_count} selected feature(s)."))
        form.addRow("Operation", self._operation_combo)
        form.addRow("Qualifier key", self._key_combo)
        form.addRow("Value", self._value_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_operation_changed(self) -> None:
        self._value_edit.setEnabled(self.operation() != "remove")

    def operation(self) -> str:
        return ["set", "add", "remove"][self._operation_combo.currentIndex()]

    def key(self) -> str:
        return self._key_combo.currentText().strip()

    def value(self) -> str:
        return self._value_edit.text()
