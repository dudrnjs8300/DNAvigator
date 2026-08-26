"""Tool Setup Wizard (minimal P0-extended form): detect installed BLAST+
executables, or let the user browse to a directory that contains them.
Never crashes or blocks when BLAST+ is absent — reports exactly what is
missing (spec 2.3 acceptance criterion).
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from genome_workbench.domain.blast_models import BlastInstallation, BlastProgram
from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES, detect_installation
from genome_workbench.infrastructure.blast.downloader import (
    DownloadCancelled,
    download_and_install,
)
from genome_workbench.infrastructure.filesystem.paths import tools_dir


class _BlastDownloadWorker(QThread):
    """Downloads+extracts the official NCBI BLAST+ Windows build off the UI
    thread (application/infrastructure code stays Qt-free; see
    ui/workers/callable_worker.py for the same pattern used by BLAST
    searches). A dedicated worker rather than CallableWorker because this is
    the only job in the app that needs incremental progress, not just
    succeeded/failed.
    """

    progress = Signal(int, int)  # bytes_downloaded, total_bytes
    succeeded = Signal(Path)
    failed = Signal(str)

    def __init__(self, destination_dir: Path) -> None:
        super().__init__()
        self._destination_dir = destination_dir
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            bin_dir = download_and_install(
                self._destination_dir,
                cancel_event=self.cancel_event,
                progress_callback=lambda done, total: self.progress.emit(done, total),
            )
        except DownloadCancelled:
            self.failed.emit("Download cancelled.")
            return
        except Exception as exc:  # noqa: BLE001 - reported to the UI, not swallowed
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(bin_dir)


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
            "This application does not bundle NCBI BLAST+. Either download the official "
            "distribution below, or install it yourself "
            "(https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/) and point this "
            "dialog at its bin directory."
        )
        info_label.setWordWrap(True)

        self._download_worker: _BlastDownloadWorker | None = None
        self._download_button = QPushButton("Download && Install BLAST+ (official NCBI build)")
        self._download_button.clicked.connect(self._on_download_clicked)
        self._download_cancel_button = QPushButton("Cancel")
        self._download_cancel_button.clicked.connect(self._on_download_cancel_clicked)
        self._download_cancel_button.setVisible(False)
        self._download_progress = QProgressBar()
        self._download_progress.setVisible(False)

        download_row = QHBoxLayout()
        download_row.addWidget(self._download_button, stretch=1)
        download_row.addWidget(self._download_cancel_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(dir_row)
        layout.addWidget(info_label)
        layout.addLayout(download_row)
        layout.addWidget(self._download_progress)
        layout.addWidget(self._status_view)
        layout.addWidget(buttons)

        self._refresh_status()

    def _on_download_clicked(self) -> None:
        destination = tools_dir() / "blast+"
        confirmed = QMessageBox.question(
            self,
            "Download BLAST+",
            "Download the official NCBI BLAST+ Windows distribution (~140 MB) from "
            "ftp.ncbi.nlm.nih.gov and install it to:\n\n"
            f"{destination}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        self._download_button.setEnabled(False)
        self._download_cancel_button.setVisible(True)
        self._download_progress.setVisible(True)
        self._download_progress.setRange(0, 0)  # indeterminate until first progress signal

        self._download_worker = _BlastDownloadWorker(destination)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.succeeded.connect(self._on_download_succeeded)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.start()

    def _on_download_cancel_clicked(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self._download_progress.setRange(0, total)
            self._download_progress.setValue(downloaded)

    def _reset_download_ui(self) -> None:
        self._download_button.setEnabled(True)
        self._download_cancel_button.setVisible(False)
        self._download_progress.setVisible(False)
        self._download_worker = None

    def _on_download_succeeded(self, bin_dir: Path) -> None:
        self._reset_download_ui()
        self._dir_edit.setText(str(bin_dir))
        self._on_detect()
        if self.installation.is_fully_installed():
            QMessageBox.information(
                self, "Download complete", f"BLAST+ installed successfully to:\n{bin_dir}"
            )
        else:
            QMessageBox.warning(
                self,
                "Download complete",
                f"BLAST+ was downloaded to:\n{bin_dir}\n\n"
                "but not every required executable was found afterward -- see the status "
                "list below.",
            )

    def _on_download_failed(self, message: str) -> None:
        self._reset_download_ui()
        if message != "Download cancelled.":
            QMessageBox.warning(self, "Download failed", message)

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
