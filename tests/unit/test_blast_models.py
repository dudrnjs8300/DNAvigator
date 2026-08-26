from genome_workbench.domain.blast_models import BlastProgram, suggest_program
from genome_workbench.domain.models import MoleculeType


def test_suggest_blastn_for_nucleotide_vs_nucleotide():
    assert suggest_program(MoleculeType.DNA, MoleculeType.DNA) == BlastProgram.BLASTN


def test_suggest_blastp_for_protein_vs_protein():
    assert suggest_program(MoleculeType.PROTEIN, MoleculeType.PROTEIN) == BlastProgram.BLASTP


def test_suggest_blastx_for_nucleotide_query_vs_protein_db():
    assert suggest_program(MoleculeType.DNA, MoleculeType.PROTEIN) == BlastProgram.BLASTX


def test_suggest_tblastn_for_protein_query_vs_nucleotide_db():
    assert suggest_program(MoleculeType.PROTEIN, MoleculeType.DNA) == BlastProgram.TBLASTN
