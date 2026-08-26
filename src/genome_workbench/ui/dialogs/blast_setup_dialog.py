"""Tool Setup Wizard (minimal P0-extended form): detect installed BLAST+
executables, or let the user browse to a directory that contains them.
Never crashes or blocks when BLAST+ is absent — reports exactly what is
missing (spec 2.3 acceptance criterion).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from genome_workbench.domain.blast_models import BlastInstallation, BlastProgram
from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES, detect_installation


class BlastSetupDialog(QDialog):
    def __init__(self, initial_search_dir: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BLAST Setup")
        self.resize(520, 420)
        self.installation: BlastInstallation = detect_installation(
            Path(initial_search_dir) if initial_search_dir else None
        )

        self._dir_edit = QLineEdit(initial_search_dir or "")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse)
        detect_button = QPushButton("Detect")
        detect_button.clicked.connect(self._on_detect)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("BLAST+ bin directory (optional, else PATH is searched):"))
        dir_row.addWidget(self._dir_edit, stretch=1)
        dir_row.addWidget(browse_button)
        dir_row.addWidget(detect_button)

        self._status_view = QPlainTextEdit()
        self._status_view.setReadOnly(True)

        info_label = QLabel(
            "This application does not bundle NCBI BLAST+. Install it yourself "
            "(https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/) and "
            "either add it to PATH or point this dialog at its bin directory."
        )
        info_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(dir_row)
        layout.addWidget(info_label)
        layout.addWidget(self._status_view)
        layout.addWidget(buttons)

        self._refresh_status()

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "BLAST+ bin directory")
        if directory:
            self._dir_edit.setText(directory)
            self._on_detect()

    def _on_detect(self) -> None:
        search_dir = Path(self._dir_edit.text()) if self._dir_edit.text() else None
        self.installation = detect_installation(search_dir)
        self._refresh_status()

    def _refresh_status(self) -> None:
        lines = []
        for name in REQUIRED_EXECUTABLES:
            if name in self.installation.executables:
                lines.append(f"[OK] {name}: {self.installation.executables[name]}")
                lines.append(f"       {self.installation.versions.get(name, '')}")
            else:
                lines.append(f"[MISSING] {name}")
        lines.append("")
        if self.installation.is_fully_installed():
            lines.append("All required executables found. BLAST features are ready to use.")
        else:
            missing = [n for n in REQUIRED_EXECUTABLES if n not in self.installation.executables]
            lines.append(f"Missing: {', '.join(missing)}")
            lines.append(
                "BLAST features will remain disabled/unavailable for the missing programs "
                "until they are installed and detected."
            )
        self._status_view.setPlainText("\n".join(lines))

    def program_available(self, program: BlastProgram) -> bool:
        return program.value in self.installation.executables
