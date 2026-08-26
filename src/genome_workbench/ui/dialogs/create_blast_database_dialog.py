"""Collects the inputs needed to build a BLAST database: source FASTA,
molecule type, and a display name. The actual ``makeblastdb`` run happens
in a worker thread owned by the caller (MainWindow), not here.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)

from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.formats.fasta_adapter import guess_molecule_type


class CreateBlastDatabaseDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create BLAST Database")

        self._source_edit = QLineEdit()
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse)
        source_row = QHBoxLayout()
        source_row.addWidget(self._source_edit, stretch=1)
        source_row.addWidget(browse_button)

        self._molecule_combo = QComboBox()
        self._molecule_combo.addItems(["nucleotide", "protein"])
        self._name_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Source FASTA", source_row)
        form.addRow("Molecule type", self._molecule_combo)
        form.addRow("Database name", self._name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow(form)
        layout.addRow(buttons)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Source FASTA", "", "FASTA (*.fasta *.fa *.fna *.faa *.fsa)"
        )
        if path:
            self._source_edit.setText(path)
            if not self._name_edit.text():
                self._name_edit.setText(Path(path).stem)
            try:
                sequence_sample = Path(path).read_text(encoding="utf-8", errors="replace")
                first_record_lines = []
                in_record = False
                for line in sequence_sample.splitlines():
                    if line.startswith(">"):
                        if in_record:
                            break
                        in_record = True
                        continue
                    if in_record:
                        first_record_lines.append(line)
                molecule_type = guess_molecule_type("".join(first_record_lines))
                if molecule_type == MoleculeType.PROTEIN:
                    self._molecule_combo.setCurrentText("protein")
                else:
                    self._molecule_combo.setCurrentText("nucleotide")
            except OSError:
                pass

    def source_fasta(self) -> Path:
        return Path(self._source_edit.text())

    def molecule_type(self) -> MoleculeType:
        return (
            MoleculeType.PROTEIN
            if self._molecule_combo.currentText() == "protein"
            else MoleculeType.DNA
        )

    def database_name(self) -> str:
        return self._name_edit.text() or "database"
