"""Pure sequence operations: reverse-complement, translation, GC content.

No Qt, no Biopython here — domain layer is format/UI independent.
"""

from __future__ import annotations

from dataclasses import dataclass

_DNA_COMPLEMENT = str.maketrans(
    "ACGTURYSWKMBDHVNacgturyswkmbdhvn-",
    "TGCAAYRSWMKVHDBNtgcaayrswmkvhdbn-",
)

# NCBI standard genetic code (table 1). Table 11 (bacterial/archaeal/plant
# plastid) shares the exact same codon->amino-acid assignments as table 1;
# they differ only in which codons are recognized as alternative start codons.
_STANDARD_CODON_TABLE: dict[str, str] = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}

_STOP_CODONS = frozenset({codon for codon, aa in _STANDARD_CODON_TABLE.items() if aa == "*"})

_START_CODONS_BY_TABLE: dict[int, frozenset[str]] = {
    1: frozenset({"ATG"}),
    11: frozenset({"ATG", "GTG", "TTG", "CTG", "ATT", "ATC", "ATA"}),
}


class UnsupportedGeneticCodeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TranslationResult:
    protein: str
    has_start_codon: bool
    has_stop_codon: bool
    internal_stop_count: int
    is_multiple_of_three: bool


def reverse_complement(sequence: str) -> str:
    return sequence.translate(_DNA_COMPLEMENT)[::-1]


def gc_content(sequence: str) -> float:
    if not sequence:
        return 0.0
    seq_upper = sequence.upper()
    gc = sum(1 for base in seq_upper if base in "GC")
    return gc / len(seq_upper)


def codon_table_for(genetic_code: int) -> dict[str, str]:
    if genetic_code not in _START_CODONS_BY_TABLE:
        raise UnsupportedGeneticCodeError(
            f"genetic code table {genetic_code} is not supported; "
            f"supported: {sorted(_START_CODONS_BY_TABLE)}"
        )
    return dict(_STANDARD_CODON_TABLE)


def start_codons_for(genetic_code: int) -> frozenset[str]:
    if genetic_code not in _START_CODONS_BY_TABLE:
        raise UnsupportedGeneticCodeError(
            f"genetic code table {genetic_code} is not supported; "
            f"supported: {sorted(_START_CODONS_BY_TABLE)}"
        )
    return _START_CODONS_BY_TABLE[genetic_code]


def translate(
    sequence: str,
    genetic_code: int = 11,
    codon_start_offset: int = 0,
    trim_trailing_stop: bool = True,
) -> TranslationResult:
    """Translate a biological (already strand-corrected) nucleotide sequence.

    ``codon_start_offset`` is 0, 1, or 2, corresponding to GenBank
    ``/codon_start`` 1, 2, 3 (i.e. codon_start - 1).
    """
    if codon_start_offset not in (0, 1, 2):
        raise ValueError(f"codon_start_offset must be 0, 1, or 2, got {codon_start_offset}")
    table = codon_table_for(genetic_code)
    starts = start_codons_for(genetic_code)

    coding = sequence.upper()[codon_start_offset:]
    is_multiple_of_three = len(coding) % 3 == 0

    first_codon = coding[0:3] if len(coding) >= 3 else ""
    has_start_codon = first_codon in starts

    residues: list[str] = []
    internal_stop_count = 0
    n_codons = len(coding) // 3
    for i in range(n_codons):
        codon = coding[i * 3 : i * 3 + 3]
        aa = table.get(codon, "X")
        is_last_codon = i == n_codons - 1
        if aa == "*":
            if is_last_codon:
                pass
            else:
                internal_stop_count += 1
            residues.append(aa)
        else:
            residues.append(aa)

    has_stop_codon = bool(residues) and residues[-1] == "*"
    protein = "".join(residues)
    if trim_trailing_stop and has_stop_codon:
        protein = protein[:-1]

    return TranslationResult(
        protein=protein,
        has_start_codon=has_start_codon,
        has_stop_codon=has_stop_codon,
        internal_stop_count=internal_stop_count,
        is_multiple_of_three=is_multiple_of_three,
    )
