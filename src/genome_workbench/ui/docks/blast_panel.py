"""Bottom panel: BLAST installation status, database catalog, search
parameters, hit table, and HSP alignment — all in one place so a BLAST run
and its results never require a separate disconnected window.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genome_workbench.domain.blast_models import (
    BlastDatabase,
    BlastHit,
    BlastInstallation,
    BlastProgram,
    BlastSearchParameters,
    BlastSearchResult,
)

_HIT_COLUMNS = ["Subject", "Title", "Identity %", "Query Cov %", "E-value", "Bit score", "HSPs"]


class BlastPanel(QDockWidget):
    setupRequested = Signal()
    createDatabaseRequested = Signal()
    runRequested = Signal()
    applyRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("BLAST", parent)
        self._databases: list[BlastDatabase] = []
        self._result: BlastSearchResult | None = None

        container = QWidget()
        layout = QHBoxLayout(container)

        layout.addWidget(self._build_setup_group())
        layout.addWidget(self._build_run_group())
        layout.addWidget(self._build_results_group(), stretch=1)

        self.setWidget(container)

    # -- Sub-panels ----------------------------------------------------------

    def _build_setup_group(self) -> QWidget:
        group = QGroupBox("Installation")
        self._installation_status_label = QLabel("Not detected")
        self._installation_status_label.setWordWrap(True)
        setup_button = QPushButton("BLAST Setup...")
        setup_button.clicked.connect(self.setupRequested)
        create_db_button = QPushButton("Create Database...")
        create_db_button.clicked.connect(self.createDatabaseRequested)
        self._database_list = QListWidget()
        self._database_list.setMaximumWidth(220)

        layout = QVBoxLayout(group)
        layout.addWidget(self._installation_status_label)
        layout.addWidget(setup_button)
        layout.addWidget(QLabel("Registered databases:"))
        layout.addWidget(self._database_list)
        layout.addWidget(create_db_button)
        group.setMaximumWidth(260)
        return group

    def _build_run_group(self) -> QWidget:
        group = QGroupBox("Run BLAST")
        self._query_context_label = QLabel("No query selected.")
        self._query_context_label.setWordWrap(True)
        self._program_combo = QComboBox()
        self._program_combo.addItems([p.value for p in BlastProgram])
        self._evalue_spin = QDoubleSpinBox()
        self._evalue_spin.setDecimals(10)
        self._evalue_spin.setRange(1e-100, 1000.0)
        self._evalue_spin.setValue(1e-5)
        self._max_targets_spin = QSpinBox()
        self._max_targets_spin.setRange(1, 5000)
        self._max_targets_spin.setValue(50)
        self._min_identity_spin = QDoubleSpinBox()
        self._min_identity_spin.setRange(0.0, 100.0)
        self._min_identity_spin.setValue(0.0)
        self._min_coverage_spin = QDoubleSpinBox()
        self._min_coverage_spin.setRange(0.0, 100.0)
        self._min_coverage_spin.setValue(0.0)
        run_button = QPushButton("Run BLAST")
        run_button.clicked.connect(self.runRequested)

        layout = QVBoxLayout(group)
        layout.addWidget(self._query_context_label)
        layout.addWidget(QLabel("Program"))
        layout.addWidget(self._program_combo)
        layout.addWidget(QLabel("E-value"))
        layout.addWidget(self._evalue_spin)
        layout.addWidget(QLabel("Max target sequences"))
        layout.addWidget(self._max_targets_spin)
        layout.addWidget(QLabel("Min identity % (display filter)"))
        layout.addWidget(self._min_identity_spin)
        layout.addWidget(QLabel("Min query coverage % (display filter)"))
        layout.addWidget(self._min_coverage_spin)
        layout.addWidget(run_button)
        group.setMaximumWidth(220)
        return group

    def _build_results_group(self) -> QWidget:
        group = QGroupBox("Results")
        self._hit_table = QTableWidget(0, len(_HIT_COLUMNS))
        self._hit_table.setHorizontalHeaderLabels(_HIT_COLUMNS)
        self._hit_table.itemSelectionChanged.connect(self._on_hit_selected)
        self._hsp_view = QPlainTextEdit()
        self._hsp_view.setReadOnly(True)
        self._hsp_view.setFont(self._hsp_view.font())
        apply_button = QPushButton("Apply as Annotation...")
        apply_button.clicked.connect(self.applyRequested)

        splitter = QSplitter()
        splitter.addWidget(self._hit_table)
        splitter.addWidget(self._hsp_view)

        layout = QVBoxLayout(group)
        layout.addWidget(splitter, stretch=1)
        layout.addWidget(apply_button)
        return group

    # -- State updates -----------------------------------------------------------

    def set_installation(self, installation: BlastInstallation) -> None:
        found = ", ".join(sorted(installation.executables)) or "none"
        status = "fully installed" if installation.is_fully_installed() else "partially installed"
        self._installation_status_label.setText(
            f"{status}\nfound: {found}\ndir: {installation.directory or '(PATH)'}"
        )

    def set_databases(self, databases: list[BlastDatabase]) -> None:
        self._databases = databases
        self._database_list.clear()
        for db in databases:
            item = QListWidgetItem(
                f"{db.name} ({db.molecule_type.value}, {db.sequence_count} seqs)"
            )
            item.setData(1000, db.id)
            self._database_list.addItem(item)

    def selected_database(self) -> BlastDatabase | None:
        item = self._database_list.currentItem()
        if item is None:
            return None
        db_id = item.data(1000)
        return next((d for d in self._databases if d.id == db_id), None)

    def set_query_context(self, description: str) -> None:
        self._query_context_label.setText(description)

    def set_suggested_program(self, program: BlastProgram) -> None:
        self._program_combo.setCurrentText(program.value)

    def selected_program(self) -> BlastProgram:
        return BlastProgram(self._program_combo.currentText())

    def search_parameters(self) -> BlastSearchParameters:
        return BlastSearchParameters(
            program=self.selected_program(),
            evalue=self._evalue_spin.value(),
            max_target_seqs=self._max_targets_spin.value(),
            min_identity=self._min_identity_spin.value(),
            min_query_coverage=self._min_coverage_spin.value(),
        )

    def set_result(self, result: BlastSearchResult) -> None:
        self._result = result
        self._hit_table.setRowCount(0)
        for hit in result.hits:
            row = self._hit_table.rowCount()
            self._hit_table.insertRow(row)
            values = [
                hit.subject_id,
                hit.subject_title,
                f"{hit.best_identity:.1f}",
                f"{hit.best_query_coverage:.1f}",
                f"{hit.best_evalue:.2e}",
                f"{hit.best_bitscore:.1f}",
                str(len(hit.hsps)),
            ]
            for col, value in enumerate(values):
                self._hit_table.setItem(row, col, QTableWidgetItem(value))
        self._hsp_view.setPlainText(f"{len(result.hits)} hit(s) found.")

    def selected_hit(self) -> BlastHit | None:
        if self._result is None:
            return None
        row = self._hit_table.currentRow()
        if row < 0 or row >= len(self._result.hits):
            return None
        return self._result.hits[row]

    def _on_hit_selected(self) -> None:
        hit = self.selected_hit()
        if hit is None:
            return
        lines = [f"Subject: {hit.subject_id}", f"Title: {hit.subject_title}", ""]
        for i, hsp in enumerate(hit.hsps):
            lines.append(
                f"HSP {i + 1}: identity {hsp.identity_pct:.1f}%  "
                f"cov {hsp.query_coverage_pct:.1f}%  evalue {hsp.evalue:.2e}  "
                f"bitscore {hsp.bitscore:.1f}  strand {hsp.subject_strand:+d}"
            )
            lines.append(f"Q: {hsp.query_seq}")
            lines.append(f"S: {hsp.subject_seq}")
            lines.append("")
        self._hsp_view.setPlainText("\n".join(lines))
