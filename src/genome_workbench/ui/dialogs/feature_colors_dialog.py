"""Lets the user customize the color used for each feature type on the
Genome Map / Circular Map / minimap -- previously the palette was a fixed
built-in dict with no way to change it (user-reported gap: distinguishing
feature types by color, and choosing the colors, matters for figures).
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genome_workbench.ui.rendering.feature_colors import DEFAULT_FEATURE_COLORS, feature_color

_TYPE_COLUMN = 0
_COLOR_COLUMN = 1
_RESET_COLUMN = 2


class FeatureColorsDialog(QDialog):
    def __init__(
        self,
        current_overrides: dict[str, str],
        extra_types: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Feature Colors")
        self.resize(420, 420)
        self.overrides: dict[str, str] = dict(current_overrides)

        types = set(DEFAULT_FEATURE_COLORS) | set(self.overrides) | set(extra_types or [])

        info = QLabel("Click a color swatch to change it. Colors are remembered across projects.")
        info.setWordWrap(True)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Feature type", "Color", ""])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().setVisible(False)

        add_type_button = QPushButton("Add Type...")
        add_type_button.clicked.connect(self._on_add_type)
        reset_all_button = QPushButton("Reset All to Defaults")
        reset_all_button.clicked.connect(self._on_reset_all)
        button_row = QHBoxLayout()
        button_row.addWidget(add_type_button)
        button_row.addWidget(reset_all_button)
        button_row.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(button_row)
        layout.addWidget(self._table, stretch=1)
        layout.addWidget(buttons)

        for feature_type in sorted(types):
            self._add_row(feature_type)

    def _current_color(self, feature_type: str) -> QColor:
        return feature_color(feature_type, self.overrides)

    def _add_row(self, feature_type: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, _TYPE_COLUMN, QTableWidgetItem(feature_type))

        swatch = QPushButton()
        swatch.setFixedWidth(70)
        swatch.clicked.connect(lambda _checked, r=row: self._on_pick_color(r))
        self._table.setCellWidget(row, _COLOR_COLUMN, swatch)

        reset = QPushButton("Reset")
        reset.clicked.connect(lambda _checked, r=row: self._on_reset_row(r))
        self._table.setCellWidget(row, _RESET_COLUMN, reset)

        self._refresh_row(row)

    def _refresh_row(self, row: int) -> None:
        item = self._table.item(row, _TYPE_COLUMN)
        assert item is not None
        feature_type = item.text()
        color = self._current_color(feature_type)
        swatch = self._table.cellWidget(row, _COLOR_COLUMN)
        assert isinstance(swatch, QPushButton)
        swatch.setText(color.name())
        text_color = "#000000" if color.lightnessF() > 0.5 else "#ffffff"
        swatch.setStyleSheet(f"background-color: {color.name()}; color: {text_color};")

    def _on_pick_color(self, row: int) -> None:
        item = self._table.item(row, _TYPE_COLUMN)
        assert item is not None
        feature_type = item.text()
        chosen = QColorDialog.getColor(
            self._current_color(feature_type), self, f"Color for {feature_type}"
        )
        if chosen.isValid():
            self.overrides[feature_type] = chosen.name()
            self._refresh_row(row)

    def _on_reset_row(self, row: int) -> None:
        item = self._table.item(row, _TYPE_COLUMN)
        assert item is not None
        feature_type = item.text()
        self.overrides.pop(feature_type, None)
        self._refresh_row(row)

    def _on_reset_all(self) -> None:
        self.overrides.clear()
        for row in range(self._table.rowCount()):
            self._refresh_row(row)

    def _on_add_type(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Add Feature Type", "Feature type (e.g. ncRNA, terminator):"
        )
        name = name.strip()
        if not ok or not name:
            return
        existing_types = {
            self._table.item(row, _TYPE_COLUMN).text()  # type: ignore[union-attr]
            for row in range(self._table.rowCount())
        }
        if name in existing_types:
            return
        self._add_row(name)
