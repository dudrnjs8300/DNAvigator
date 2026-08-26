"""Non-destructive sequence operations on the current selection (spec 10.1):
copy, reverse-complement, translate, export-as-FASTA. None of these mutate
the record; they back the canvas's selection context menu.
"""

from __future__ import annotations

from pathlib import Path

from genome_workbench.domain.models import SequenceRecord, Topology
from genome_workbench.domain.sequence_ops import reverse_complement, translate
from genome_workbench.infrastructure.filesystem.atomic_write import write_atomic
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_text


class SequenceOperationsService:
    def get_selection(self, record: SequenceRecord, start0: int, end0: int) -> str:
        return record.sequence[start0:end0]

    def get_selection_reverse_complement(
        self, record: SequenceRecord, start0: int, end0: int
    ) -> str:
        return reverse_complement(record.sequence[start0:end0])

    def get_selection_translation(
        self,
        record: SequenceRecord,
        start0: int,
        end0: int,
        strand: int = 1,
        genetic_code: int = 11,
    ) -> str:
        sequence = record.sequence[start0:end0]
        if strand == -1:
            sequence = reverse_complement(sequence)
        return translate(sequence, genetic_code=genetic_code).protein

    def export_selection_fasta(
        self,
        record: SequenceRecord,
        start0: int,
        end0: int,
        destination: Path,
        strand: int = 1,
    ) -> None:
        sequence = self.get_selection(record, start0, end0)
        if strand == -1:
            sequence = reverse_complement(sequence)
        header = f">{record.display_id}:{start0 + 1}-{end0}{'(-)' if strand == -1 else ''}"
        wrapped = "\n".join(sequence[i : i + 70] for i in range(0, len(sequence), 70))
        content = f"{header}\n{wrapped}\n"

        def write_fasta(path: Path) -> None:
            path.write_text(content, encoding="utf-8")

        write_atomic(Path(destination), write_fasta)

    def extract_as_new_record(
        self,
        record: SequenceRecord,
        start0: int,
        end0: int,
        strand: int = 1,
        new_display_id: str | None = None,
    ) -> SequenceRecord:
        """Non-destructive: builds a new, unpersisted record from a selection
        of ``record`` (spec 10.1). The original record is untouched; the
        caller (UI) persists the result via the project repository."""
        sequence = self.get_selection(record, start0, end0)
        if strand == -1:
            sequence = reverse_complement(sequence)
        display_id = new_display_id or f"{record.display_id}_{start0 + 1}-{end0}"
        strand_suffix = "(-)" if strand == -1 else ""
        return SequenceRecord(
            display_id=display_id,
            name=display_id,
            description=f"Extracted from {record.display_id}:{start0 + 1}-{end0}{strand_suffix}",
            molecule_type=record.molecule_type,
            topology=Topology.LINEAR,
            sequence=sequence,
            checksum_sha256=sha256_of_text(sequence),
            source_format=record.source_format,
        )

    def reverse_complement_as_new_record(
        self, record: SequenceRecord, new_display_id: str | None = None
    ) -> SequenceRecord:
        """Non-destructive: builds a new, unpersisted record holding the
        reverse complement of the whole ``record`` (spec 10.1)."""
        sequence = reverse_complement(record.sequence)
        display_id = new_display_id or f"{record.display_id}_rc"
        return SequenceRecord(
            display_id=display_id,
            name=display_id,
            description=f"Reverse complement of {record.display_id}",
            molecule_type=record.molecule_type,
            topology=record.topology,
            sequence=sequence,
            checksum_sha256=sha256_of_text(sequence),
            source_format=record.source_format,
        )
