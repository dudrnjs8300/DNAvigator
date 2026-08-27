"""Non-destructive sequence operations on the current selection (spec 10.1):
copy, reverse-complement, translate, export-as-FASTA. None of these mutate
the record; they back the canvas's selection context menu.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from genome_workbench.domain.locations import LocationPart, order_parts_for_strand
from genome_workbench.domain.models import Feature, SequenceRecord, Topology, new_id, utc_now
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

    def extract_as_new_record_with_features(
        self,
        record: SequenceRecord,
        features: list[Feature],
        start0: int,
        end0: int,
        strand: int = 1,
        new_display_id: str | None = None,
    ) -> tuple[SequenceRecord, list[Feature]]:
        """Like :meth:`extract_as_new_record`, but also carries over the
        features that fall fully within ``[start0, end0)``, rebased into the
        new record's own coordinate frame -- previously extracting a
        selection as a new record silently dropped every annotation in it
        (user-reported gap: copying a region should bring its gene calls
        along, not just the raw bases).

        Returned features have ``record_id=""`` -- the caller sets it to the
        new record's real id (only known after construction) before saving.
        """
        new_record = self.extract_as_new_record(record, start0, end0, strand, new_display_id)
        new_features = self._extract_features_for_range(features, start0, end0, strand)
        return new_record, new_features

    def _extract_features_for_range(
        self, features: list[Feature], start0: int, end0: int, strand: int
    ) -> list[Feature]:
        """Copies of the features fully contained within ``[start0, end0)``,
        rebased to the extracted region's own 0-based coordinate frame (and,
        for ``strand=-1``, mirrored the same way the sequence itself is
        reverse-complemented -- see D-002 in docs/DECISIONS.md). Features
        that only partially overlap the range are dropped rather than
        silently truncated into something that no longer matches its
        original biological meaning (e.g. a CDS missing its stop codon).
        """
        region_length = end0 - start0
        extracted: list[Feature] = []
        for feature in features:
            if not feature.parts:
                continue
            if not all(start0 <= p.start0 and p.end0 <= end0 for p in feature.parts):
                continue
            ascending = sorted(feature.parts, key=lambda p: p.start0)
            if strand == -1:
                rebased = [
                    LocationPart(
                        start0=region_length - (p.end0 - start0),
                        end0=region_length - (p.start0 - start0),
                        order_index=0,
                        fuzzy_start=p.fuzzy_end,
                        fuzzy_end=p.fuzzy_start,
                        phase=p.phase,
                    )
                    for p in ascending
                ]
                rebased.sort(key=lambda p: p.start0)
                new_strand = None if feature.strand is None else -feature.strand
            else:
                rebased = [
                    LocationPart(
                        start0=p.start0 - start0,
                        end0=p.end0 - start0,
                        order_index=0,
                        fuzzy_start=p.fuzzy_start,
                        fuzzy_end=p.fuzzy_end,
                        phase=p.phase,
                    )
                    for p in ascending
                ]
                new_strand = feature.strand
            ordered_parts = order_parts_for_strand(rebased, new_strand)
            extracted.append(
                replace(
                    feature,
                    id=new_id(),
                    record_id="",
                    parts=ordered_parts,
                    strand=new_strand,
                    qualifiers=feature.qualifiers.copy(),
                    parent_ids=[],
                    child_ids=[],
                    provenance_id=None,
                    created_at=utc_now(),
                    modified_at=utc_now(),
                    revision=0,
                )
            )
        return extracted

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
