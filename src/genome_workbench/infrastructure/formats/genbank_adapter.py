"""GenBank import/export adapter built on Biopython's SeqIO.

Biopython's ``CompoundLocation.parts`` order already matches this project's
domain convention (see :mod:`genome_workbench.domain.locations`): parts are
held internally in biological 5'->3' order (descending genomic order for a
uniformly reverse-strand compound feature), and Biopython's own reader/writer
transparently handle the ascending-order GenBank text <-> biological-order
internal-object conversion via how ``complement()`` wraps ``join()``. This was
verified empirically against Biopython 1.88 (see docs/DECISIONS.md D-002)
before writing this adapter, so no additional part-reordering is done here in
either direction — the adapter trusts Biopython's part order completely.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import (
    AfterPosition,
    BeforePosition,
    CompoundLocation,
    ExactPosition,
    Reference,
    SeqFeature,
    SimpleLocation,
)
from Bio.SeqRecord import SeqRecord

from genome_workbench.domain.locations import LocationOperator, LocationPart
from genome_workbench.domain.models import (
    Feature,
    MoleculeType,
    SequenceRecord,
    Topology,
)
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_text
from genome_workbench.infrastructure.formats.format_sniffer import is_gzipped
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity


@dataclass(slots=True)
class GenbankImportResult:
    records: list[SequenceRecord] = field(default_factory=list)
    features_by_record_id: dict[str, list[Feature]] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)


_MOLECULE_TYPE_TO_DOMAIN = {
    "protein": MoleculeType.PROTEIN,
}


def _map_molecule_type(raw: str) -> MoleculeType:
    lowered = (raw or "").lower()
    if "protein" in lowered:
        return MoleculeType.PROTEIN
    if "rna" in lowered:
        return MoleculeType.RNA
    if "dna" in lowered or lowered == "":
        return MoleculeType.DNA
    return MoleculeType.UNKNOWN


def _map_topology(raw: str) -> Topology:
    lowered = (raw or "linear").lower()
    if lowered == "circular":
        return Topology.CIRCULAR
    if lowered == "linear":
        return Topology.LINEAR
    return Topology.UNKNOWN


def _domain_molecule_type_to_genbank(molecule_type: MoleculeType) -> str:
    return {
        MoleculeType.DNA: "DNA",
        MoleculeType.RNA: "RNA",
        MoleculeType.PROTEIN: "protein",
        MoleculeType.UNKNOWN: "DNA",
    }[molecule_type]


def read_genbank(path: Path, record_id_generator=None) -> GenbankImportResult:
    """Import all records from a (optionally gzipped) multi-record GenBank file.

    ``record_id_generator`` overrides internal UUID generation; used by tests
    for deterministic IDs. Malformed individual features do not abort the
    whole record (lenient import): they are reported as issues and skipped.
    """
    from genome_workbench.domain.models import new_id

    make_id = record_id_generator or new_id
    path = Path(path)
    result = GenbankImportResult()

    opener = gzip.open if is_gzipped(path) else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace") as handle:
        bio_records = list(SeqIO.parse(handle, "genbank"))

    if not bio_records:
        result.issues.append(
            ImportIssue(
                ImportSeverity.ERROR, "no_records_found", "No GenBank records found in file"
            )
        )
        return result

    for index, bio_record in enumerate(bio_records):
        record_id = make_id()
        sequence = str(bio_record.seq).upper()
        molecule_type = _map_molecule_type(bio_record.annotations.get("molecule_type", ""))
        topology = _map_topology(bio_record.annotations.get("topology", "linear"))

        record = SequenceRecord(
            id=record_id,
            display_id=bio_record.id,
            name=bio_record.name or bio_record.id,
            description=bio_record.description,
            molecule_type=molecule_type,
            topology=topology,
            sequence=sequence,
            checksum_sha256=sha256_of_text(sequence),
            annotations_json=_extract_annotations_json(bio_record),
            source_format="genbank",
            source_record_index=index,
        )
        result.records.append(record)

        features: list[Feature] = []
        for bio_feature in bio_record.features:
            try:
                feature = _convert_bio_feature(bio_feature, record_id, make_id, len(sequence))
            except Exception as exc:  # noqa: BLE001 - malformed feature must not abort import
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "feature_import_failed",
                        f"Skipped unparseable feature ({bio_feature.type}): {exc}",
                        record.display_id,
                    )
                )
                continue
            features.append(feature)
        result.features_by_record_id[record_id] = features

    return result


def _extract_annotations_json(bio_record: SeqRecord) -> str:
    # Biopython's own SeqRecord.annotations type hint (str | int) is narrower
    # than what it actually stores at runtime (also list, e.g. taxonomy/
    # references) — this is a known imprecision in Biopython's stubs.
    references = []
    raw_references: object = bio_record.annotations.get("references", [])
    for ref in raw_references if isinstance(raw_references, list) else []:
        references.append(
            {
                "authors": getattr(ref, "authors", "") or "",
                "title": getattr(ref, "title", "") or "",
                "journal": getattr(ref, "journal", "") or "",
                "pubmed_id": getattr(ref, "pubmed_id", "") or "",
                "medline_id": getattr(ref, "medline_id", "") or "",
                "comment": getattr(ref, "comment", "") or "",
            }
        )
    data = {
        "organism": bio_record.annotations.get("organism", ""),
        "taxonomy": bio_record.annotations.get("taxonomy", []),
        "source": bio_record.annotations.get("source", ""),
        "keywords": bio_record.annotations.get("keywords", []),
        "accessions": bio_record.annotations.get("accessions", []),
        "sequence_version": bio_record.annotations.get("sequence_version"),
        "date": bio_record.annotations.get("date", ""),
        "data_file_division": bio_record.annotations.get("data_file_division", ""),
        "comment": bio_record.annotations.get("comment", ""),
        "references": references,
    }
    return json.dumps(data)


def _apply_record_annotations(bio_record: SeqRecord, annotations_json: str) -> None:
    try:
        data = json.loads(annotations_json) if annotations_json else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        return

    string_fields = (
        "organism",
        "source",
        "date",
        "data_file_division",
        "comment",
    )
    for field_name in string_fields:
        value = data.get(field_name)
        if value:
            bio_record.annotations[field_name] = value

    for list_field in ("taxonomy", "keywords", "accessions"):
        value = data.get(list_field)
        if value:
            bio_record.annotations[list_field] = value

    if data.get("sequence_version") is not None:
        bio_record.annotations["sequence_version"] = data["sequence_version"]

    references_data = data.get("references") or []
    reference_objects = []
    for ref_data in references_data:
        reference = Reference()
        reference.authors = ref_data.get("authors", "")
        reference.title = ref_data.get("title", "")
        reference.journal = ref_data.get("journal", "")
        reference.pubmed_id = ref_data.get("pubmed_id", "")
        reference.medline_id = ref_data.get("medline_id", "")
        reference.comment = ref_data.get("comment", "")
        reference_objects.append(reference)
    if reference_objects:
        bio_record.annotations["references"] = reference_objects  # type: ignore[assignment]


def _convert_bio_feature(
    bio_feature: SeqFeature, record_id: str, make_id, record_length: int
) -> Feature:
    location = bio_feature.location
    if isinstance(location, CompoundLocation):
        operator = LocationOperator(location.operator)
        raw_parts = list(location.parts)
    else:
        operator = LocationOperator.SIMPLE
        raw_parts = [location]

    strands = {p.strand for p in raw_parts if p.strand is not None}
    strand = strands.pop() if len(strands) == 1 else (raw_parts[0].strand if raw_parts else None)

    parts = [
        LocationPart(
            start0=int(part.start),
            end0=int(part.end),
            order_index=i,
            fuzzy_start=not isinstance(part.start, ExactPosition),
            fuzzy_end=not isinstance(part.end, ExactPosition),
        )
        for i, part in enumerate(raw_parts)
    ]

    qualifiers = QualifierSet()
    for key, values in bio_feature.qualifiers.items():
        if isinstance(values, list):
            for value in values:
                qualifiers.add(key, str(value))
        else:
            qualifiers.add(key, str(values))

    phase = None
    codon_start = qualifiers.get_first("codon_start")
    if codon_start is not None:
        try:
            phase = int(codon_start) - 1
        except ValueError:
            phase = None

    return Feature(
        id=make_id(),
        record_id=record_id,
        type=bio_feature.type,
        strand=strand,
        location_operator=operator,
        parts=parts,
        qualifiers=qualifiers,
        source=None,
        phase=phase,
    )


def write_genbank(
    records: list[SequenceRecord],
    features_by_record_id: dict[str, list[Feature]],
    destination: Path,
) -> None:
    """Write records + features to ``destination`` as a (possibly multi-record) GenBank file.

    Callers requiring atomic export must pass a temp path and move it into
    place themselves (see application/export_service.py).
    """
    bio_records = [
        _build_bio_record(record, features_by_record_id.get(record.id, [])) for record in records
    ]
    with open(destination, "w", encoding="utf-8") as handle:
        SeqIO.write(bio_records, handle, "genbank")


def _build_bio_record(record: SequenceRecord, features: list[Feature]) -> SeqRecord:
    bio_record = SeqRecord(
        Seq(record.sequence),
        id=record.display_id or record.id,
        name=(record.name or record.display_id or record.id)[:16],
        description=record.description or "",
    )
    bio_record.annotations["molecule_type"] = _domain_molecule_type_to_genbank(record.molecule_type)
    bio_record.annotations["topology"] = (
        record.topology.value if record.topology != Topology.UNKNOWN else "linear"
    )
    _apply_record_annotations(bio_record, record.annotations_json)

    for feature in features:
        bio_record.features.append(_build_bio_feature(feature))
    return bio_record


def _build_bio_feature(feature: Feature) -> SeqFeature:
    def build_position(value: int, fuzzy: bool, is_start: bool):
        if not fuzzy:
            return ExactPosition(value)
        return BeforePosition(value) if is_start else AfterPosition(value)

    sub_locations = [
        SimpleLocation(
            build_position(part.start0, part.fuzzy_start, is_start=True),
            build_position(part.end0, part.fuzzy_end, is_start=False),
            strand=feature.strand,
        )
        for part in sorted(feature.parts, key=lambda p: p.order_index)
    ]

    location = (
        sub_locations[0]
        if len(sub_locations) == 1
        else CompoundLocation(sub_locations, operator=feature.location_operator.value)
    )

    qualifiers: dict[str, list[str]] = {}
    for key, values in feature.qualifiers.items():
        qualifiers[key] = list(values)

    return SeqFeature(location, type=feature.type, qualifiers=qualifiers)
