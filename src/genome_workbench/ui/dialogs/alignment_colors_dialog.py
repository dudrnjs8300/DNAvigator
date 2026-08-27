"""Lets the user customize the per-residue color used in the Alignment View --
same shape as FeatureColorsDialog, scoped to whichever palette (nucleotide or
amino acid) matches the alignment currently open, since that's the only one
relevant at a time.
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

from genome_workbench.domain.models import MoleculeType
from genome_workbench.ui.rendering.nucleotide_colors import (
    DEFAULT_AMINO_ACID_COLORS,
    DEFAULT_NUCLEOTIDE_COLORS,
    residue_color,
)

_RESIDUE_COLUMN = 0
_COLOR_COLUMN = 1
_RESET_COLUMN = 2


class AlignmentColorsDialog(QDialog):
    def __init__(
        self,
        current_overrides: dict[str, str],
        molecule_type: MoleculeType,
        extra_residues: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._molecule_type = molecule_type
        label = "Amino Acid" if molecule_type == MoleculeType.PROTEIN else "Nucleotide"
        self.setWindowTitle(f"Alignment Colors ({label})")
        self.resize(380, 420)
        self.overrides: dict[str, str] = dict(current_overrides)

        defaults = (
            DEFAULT_AMINO_ACID_COLORS
            if molecule_type == MoleculeType.PROTEIN
            else DEFAULT_NUCLEOTIDE_COLORS
        )
        residues = set(defaults) | set(self.overrides) | set(extra_residues or [])

        info = QLabel(
            "Click a color swatch to change it. Matching cells are shown dimmed "
            "and mismatches at full color, so differences stand out; this only "
            "changes each residue's base color. Colors are remembered across projects."
        )
        info.setWordWrap(True)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Residue", "Color", ""])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.verticalHeader().setVisible(False)

        add_button = QPushButton("Add Residue...")
        add_button.clicked.connect(self._on_add_residue)
        reset_all_button = QPushButton("Reset All to Defaults")
        reset_all_button.clicked.connect(self._on_reset_all)
        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
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

        for residue in sorted(residues):
            self._add_row(residue)

    def _current_color(self, residue: str) -> QColor:
        return residue_color(residue, self._molecule_type, self.overrides)

    def _add_row(self, residue: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, _RESIDUE_COLUMN, QTableWidgetItem(residue))

        swatch = QPushButton()
        swatch.setFixedWidth(70)
        swatch.clicked.connect(lambda _checked, r=row: self._on_pick_color(r))
        self._table.setCellWidget(row, _COLOR_COLUMN, swatch)

        reset = QPushButton("Reset")
        reset.clicked.connect(lambda _checked, r=row: self._on_reset_row(r))
        self._table.setCellWidget(row, _RESET_COLUMN, reset)

        self._refresh_row(row)

    def _refresh_row(self, row: int) -> None:
        item = self._table.item(row, _RESIDUE_COLUMN)
        assert item is not None
        residue = item.text()
        color = self._current_color(residue)
        swatch = self._table.cellWidget(row, _COLOR_COLUMN)
        assert isinstance(swatch, QPushButton)
        swatch.setText(color.name())
        text_color = "#000000" if color.lightnessF() > 0.5 else "#ffffff"
        swatch.setStyleSheet(f"background-color: {color.name()}; color: {text_color};")

    def _on_pick_color(self, row: int) -> None:
        item = self._table.item(row, _RESIDUE_COLUMN)
        assert item is not None
        residue = item.text()
        chosen = QColorDialog.getColor(self._current_color(residue), self, f"Color for {residue}")
        if chosen.isValid():
            self.overrides[residue] = chosen.name()
            self._refresh_row(row)

    def _on_reset_row(self, row: int) -> None:
        item = self._table.item(row, _RESIDUE_COLUMN)
        assert item is not None
        residue = item.text()
        self.overrides.pop(residue, None)
        self._refresh_row(row)

    def _on_reset_all(self) -> None:
        self.overrides.clear()
        for row in range(self._table.rowCount()):
            self._refresh_row(row)

    def _on_add_residue(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Residue", "Residue letter (e.g. X):")
        name = name.strip().upper()
        if not ok or not name:
            return
        existing = {
            self._table.item(row, _RESIDUE_COLUMN).text()  # type: ignore[union-attr]
            for row in range(self._table.rowCount())
        }
        if name in existing:
            return
        self._add_row(name)
