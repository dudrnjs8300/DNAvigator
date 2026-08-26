"""Parses the custom outfmt 6 tabular output (command_builder.OUTFMT_SPEC).

Column order: qseqid sseqid pident length mismatch gapopen qstart qend sstart
send evalue bitscore qlen slen qcovhsp nident positive gaps frames qseq sseq
stitle (21 columns not counting the trailing stitle, which is column 22 and
may itself contain no further tabs).

BLAST reports 1-based inclusive query/subject coordinates, and for minus-
strand subject hits, sstart > send (the pair is reversed rather than a
separate strand column). Coordinates are converted here to this project's
canonical 0-based half-open representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genome_workbench.domain.blast_models import BlastHit, BlastHsp
from genome_workbench.domain.coordinates import internal_from_display

_EXPECTED_COLUMNS = 21  # everything up to and including sseq; stitle is the 22nd (optional)


@dataclass(slots=True)
class ParseIssue:
    line_number: int
    message: str


@dataclass(slots=True)
class ParseResult:
    hits: list[BlastHit] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)


def parse_tabular_output(text: str) -> ParseResult:
    result = ParseResult()
    hits_by_subject: dict[str, BlastHit] = {}
    order: list[str] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < _EXPECTED_COLUMNS:
            result.issues.append(
                ParseIssue(
                    line_number, f"expected >= {_EXPECTED_COLUMNS} columns, got {len(columns)}"
                )
            )
            continue
        try:
            hsp, subject_id, subject_title = _parse_row(columns)
        except ValueError as exc:
            result.issues.append(ParseIssue(line_number, f"malformed row: {exc}"))
            continue

        if subject_id not in hits_by_subject:
            hits_by_subject[subject_id] = BlastHit(
                subject_id=subject_id, subject_title=subject_title
            )
            order.append(subject_id)
        hits_by_subject[subject_id].hsps.append(hsp)

    result.hits = [hits_by_subject[sid] for sid in order]
    return result


def _parse_row(columns: list[str]) -> tuple[BlastHsp, str, str]:
    subject_id = columns[1]
    subject_title = columns[21] if len(columns) > 21 else subject_id

    qstart, qend = int(columns[6]), int(columns[7])
    q_start0, q_end0 = internal_from_display(min(qstart, qend), max(qstart, qend))

    sstart_raw, send_raw = int(columns[8]), int(columns[9])
    subject_strand = 1 if sstart_raw <= send_raw else -1
    sstart, send = min(sstart_raw, send_raw), max(sstart_raw, send_raw)
    s_start0, s_end0 = internal_from_display(sstart, send)

    hsp = BlastHsp(
        query_start0=q_start0,
        query_end0=q_end0,
        subject_start0=s_start0,
        subject_end0=s_end0,
        subject_strand=subject_strand,
        identity_pct=float(columns[2]),
        align_length=int(columns[3]),
        mismatches=int(columns[4]),
        gap_opens=int(columns[5]),
        evalue=float(columns[10]),
        bitscore=float(columns[11]),
        query_length=int(columns[12]),
        subject_length=int(columns[13]),
        query_coverage_pct=float(columns[14]),
        query_seq=columns[19],
        subject_seq=columns[20],
        frames=columns[18],
    )
    return hsp, subject_id, subject_title
