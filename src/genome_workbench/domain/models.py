"""Canonical domain entities. No Qt, no Biopython, no file-format concepts here."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from genome_workbench.domain.locations import LocationOperator, LocationPart, sorted_parts
from genome_workbench.domain.qualifiers import QualifierSet


class MoleculeType(str, Enum):
    DNA = "dna"
    RNA = "rna"
    PROTEIN = "protein"
    UNKNOWN = "unknown"


class Topology(str, Enum):
    LINEAR = "linear"
    CIRCULAR = "circular"
    UNKNOWN = "unknown"


class ProvenanceKind(str, Enum):
    IMPORT = "import"
    MANUAL = "manual"
    BLAST = "blast"
    SEQUENCE_EDIT = "sequence_edit"
    BATCH_RULE = "batch_rule"


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Provenance:
    id: str = field(default_factory=new_id)
    kind: ProvenanceKind = ProvenanceKind.MANUAL
    tool_name: str | None = None
    tool_version: str | None = None
    database_id: str | None = None
    database_checksum: str | None = None
    query_checksum: str | None = None
    parameters_json: str | None = None
    subject_id: str | None = None
    identity: float | None = None
    query_coverage: float | None = None
    subject_coverage: float | None = None
    evalue: float | None = None
    bitscore: float | None = None
    raw_result_ref: str | None = None
    created_at: str = field(default_factory=utc_now)
    user_note: str | None = None


@dataclass(slots=True)
class Folder:
    """A purely organizational grouping in the Project Explorer tree.

    Deleting a folder never deletes the records/subfolders inside it --
    callers move the contents up to the parent first (see
    ProjectService.delete_folder) so a folder is safe to remove without any
    risk of losing sequence data.
    """

    id: str = field(default_factory=new_id)
    name: str = "New Folder"
    parent_folder_id: str | None = None
    sort_order: int = 0
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class SequenceRecord:
    id: str = field(default_factory=new_id)
    display_id: str = ""
    name: str = ""
    description: str = ""
    molecule_type: MoleculeType = MoleculeType.UNKNOWN
    topology: Topology = Topology.UNKNOWN
    sequence: str = ""
    checksum_sha256: str = ""
    annotations_json: str = "{}"
    source_format: str = ""
    source_record_index: int = 0
    revision: int = 0
    folder_id: str | None = None

    @property
    def length(self) -> int:
        return len(self.sequence)


@dataclass(slots=True)
class Feature:
    id: str = field(default_factory=new_id)
    record_id: str = ""
    type: str = "misc_feature"
    strand: int | None = 1
    location_operator: LocationOperator = LocationOperator.SIMPLE
    parts: list[LocationPart] = field(default_factory=list)
    qualifiers: QualifierSet = field(default_factory=QualifierSet)
    display_label: str | None = None
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    source: str | None = None
    score: float | None = None
    phase: int | None = None
    provenance_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    revision: int = 0

    @property
    def start0(self) -> int:
        return sorted_parts(self.parts)[0].start0

    @property
    def end0(self) -> int:
        return max(p.end0 for p in self.parts)

    @property
    def length(self) -> int:
        return sum(p.length for p in self.parts)

    def computed_label(self) -> str:
        if self.display_label:
            return self.display_label
        for key in ("gene", "locus_tag", "product"):
            value = self.qualifiers.get_first(key)
            if value:
                return value
        return self.type


@dataclass(slots=True)
class Alignment:
    """A multiple sequence alignment imported as a unit (e.g. from a Clustal
    or aligned-FASTA file). Lives alongside SequenceRecord in the same
    project/folder tree -- it is its own kind of Project Explorer item, not
    a bag of loose records, because the whole point is comparing the rows
    together.
    """

    id: str = field(default_factory=new_id)
    name: str = ""
    molecule_type: MoleculeType = MoleculeType.UNKNOWN
    length: int = 0  # alignment columns, including gaps -- same for every row
    source_format: str = ""
    folder_id: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class AlignmentSequence:
    id: str = field(default_factory=new_id)
    alignment_id: str = ""
    label: str = ""
    sequence: str = ""  # aligned, gap characters ('-') included, length == Alignment.length
    order_index: int = 0


@dataclass(slots=True)
class Project:
    id: str = field(default_factory=new_id)
    name: str = "Untitled Project"
    schema_version: int = 1
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    app_version: str = ""
    settings_json: str = "{}"
    source_manifest: str = "[]"
