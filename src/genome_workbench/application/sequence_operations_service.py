"""Non-destructive sequence operations on the current selection (spec 10.1):
copy, reverse-complement, translate, export-as-FASTA. None of these mutate
the record; they back the canvas's selection context menu.
"""

from __future__ import annotations

from pathlib import Path

from genome_workbench.domain.models import SequenceRecord
from genome_workbench.domain.sequence_ops import reverse_complement, translate
from genome_workbench.infrastructure.filesystem.atomic_write import write_atomic


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
