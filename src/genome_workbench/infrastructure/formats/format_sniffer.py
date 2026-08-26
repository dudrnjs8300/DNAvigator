"""File format detection: never trust the extension alone.

Uses gzip magic bytes, BOM/CRLF-tolerant text decoding, and the first
meaningful line to classify a file before any format-specific parser runs.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_GZIP_MAGIC = b"\x1f\x8b"


class DetectedFormat(str, Enum):
    FASTA_NUCLEOTIDE = "fasta_nucleotide"
    FASTA_PROTEIN = "fasta_protein"
    FASTA_GENERIC = "fasta_generic"
    GENBANK = "genbank"
    GFF3 = "gff3"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SniffResult:
    detected_format: DetectedFormat
    is_gzipped: bool
    detail: str = ""


def _open_text(path: Path, is_gzipped: bool):
    if is_gzipped:
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8-sig", errors="replace")


def is_gzipped(path: Path) -> bool:
    with open(path, "rb") as handle:
        header = handle.read(2)
    return header == _GZIP_MAGIC


def sniff_path(path: Path) -> SniffResult:
    path = Path(path)
    gzipped = is_gzipped(path)

    try:
        with _open_text(path, gzipped) as handle:
            lines: list[str] = []
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip("\r\n")
                if stripped.strip():
                    lines.append(stripped)
                if len(lines) >= 5:
                    break
    except (OSError, UnicodeDecodeError) as exc:
        return SniffResult(DetectedFormat.UNKNOWN, gzipped, f"unreadable: {exc}")

    if not lines:
        return SniffResult(DetectedFormat.UNKNOWN, gzipped, "empty file")

    first = lines[0]

    if first.startswith(">"):
        return SniffResult(DetectedFormat.FASTA_GENERIC, gzipped, "starts with '>'")

    if first.startswith("LOCUS"):
        return SniffResult(DetectedFormat.GENBANK, gzipped, "starts with LOCUS")

    if first.startswith("##gff-version"):
        return SniffResult(DetectedFormat.GFF3, gzipped, "##gff-version directive")

    if _looks_like_gff3_body(lines):
        return SniffResult(
            DetectedFormat.GFF3,
            gzipped,
            "9-column tab-separated body without ##gff-version header",
        )

    detail = f"unrecognized first line: {first[:40]!r}"
    return SniffResult(DetectedFormat.UNKNOWN, gzipped, detail)


def _looks_like_gff3_body(lines: list[str]) -> bool:
    for line in lines:
        if line.startswith("#"):
            continue
        columns = line.split("\t")
        return len(columns) == 9
    return False
