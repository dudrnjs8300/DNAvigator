# 형식 지원 현황 (Phase 2 완료 기준)

이 문서는 실제 코드가 지원하는 범위만 기록하며, 지원하지 않는 것을 지원한다고 표시하지 않는다
(`docs/PRODUCT_SPEC.md` 25.4 금지사항).

## 입력 형식

| 형식 | 확장자 | 상태 | 비고 |
|---|---|---|---|
| Nucleotide/Protein FASTA | `.fasta`, `.fa`, `.fna`, `.ffn`, `.fnn`, `.fas`, `.fsa`, `.faa` 및 `.gz` | 지원 | `infrastructure/formats/fasta_adapter.py`. Molecule type은 alphabet 기반 추정(`guess_molecule_type`), IUPAC ambiguous nucleotide 허용. |
| GenBank | `.gb`, `.gbk`, `.genbank`, `.gbff` 및 `.gz` | 지원 | `infrastructure/formats/genbank_adapter.py`. Multi-record import. Compound(join)/reverse-strand/fuzzy(Before/After) location. Record-level metadata(organism/taxonomy/source/keywords/accessions/comment/references)를 `annotations_json`에 보존. |
| GFF3 | `.gff`, `.gff3` 및 `.gz` | 지원 | `infrastructure/formats/gff3_adapter.py`. 9-column, directive 보존, embedded(`##FASTA`)/separate FASTA pairing, discontinuous feature(같은 ID의 여러 줄) → compound location, Parent/child 관계, cycle 검출, percent-escaping. `##gff-version 3` 헤더가 없으면 명시적으로 거부한다(GFF2 등을 조용히 오해석하지 않음). |
| Generic FASTA (확장자 무관) | — | 지원 | `format_sniffer.py`가 magic bytes/첫 줄로 판별. |

GTF/EMBL/BED는 P0/P1 범위 밖이며 지원하지 않는다.

## 출력 형식

| 형식 | 상태 | 비고 |
|---|---|---|
| GenBank | 지원 | `write_genbank`. Export 전 temp file에 쓴 뒤 reimport하여 semantic diff를 검사하고, 오류가 없을 때만 atomic replace한다(`application/export_service.py`). |
| GFF3 | 지원 | `write_gff3`. `embed_fasta=True`(단일 파일, `##FASTA` 포함)와 `embed_fasta=False`(annotation-only, 별도 FASTA) 모두 지원, 동일한 semantic round-trip 검증을 거친다. |
| Nucleotide/Protein FASTA, FFN, feature table CSV/TSV | 미지원 | Phase 7 예정. |

## 보존되는 것 (검증됨)

- Sequence content, molecule type(DNA/RNA/protein), topology(linear/circular)
- Feature type, strand, simple/join location, order_index
- Qualifier: key 순서, multi-value 순서, flag qualifier(빈 값), 알 수 없는 custom qualifier
- Compound reverse-strand feature의 생물학적 추출 서열/translation (D-002 규칙 — `docs/DECISIONS.md`. GFF3의 discontinuous feature도 동일 규칙 적용)
- Fuzzy position: GenBank `BeforePosition`/`AfterPosition`
- GFF3 Parent/child 관계 (`semantic_compare.py`가 position 기반으로 비교)
- CDS phase (GFF3 phase column ↔ GenBank `/codon_start` 상호 변환)
- GenBank record-level metadata: organism, taxonomy, source, keywords, accessions, comment, references(저자/제목/저널/PMID)

## 알려진 손실/미보존 (현재 시점)

- `/translation`과 재계산 translation의 불일치 감지는 validation issue로 나타나지만(9.3절), export 시 자동 비교 리포트는 UI에 아직 노출되지 않음(Phase 4/7)
- GFF3 `Target`, `Gap`, `Derives_from`, `Is_circular` 속성은 다른 qualifier와 동일하게 key/value로 보존되지만 도메인 모델에서 특별한 의미로 해석되지는 않음(예: `Is_circular=true`가 record topology를 자동으로 바꾸지 않음)

## 테스트된 fixture (spec 16.2 목록 전부, `scratch/generate_fixtures.py`로 생성)

- `simple_linear.fasta`, `multi_contig.fasta`(중복 ID 포함), `protein_set.faa`
- `annotated_linear.gbk`(+/- strand, source/gene/CDS/tRNA/rRNA), `circular_origin.gbk`(origin-spanning joined CDS), `compound_fuzzy.gbk`(join + fuzzy location)
- `annotated_embedded.gff3`(embedded FASTA, gene→mRNA→CDS Parent chain), `annotation_only.gff3` + `matching.fna`(separate FASTA pairing)
- `invalid_coordinates.gff3`(잘못된 좌표/phase — 오류 없이 issue로 보고되는지 검증)
- `duplicate_ids.fasta`, `unicode_경로 테스트/균주 A.gbk`(한글 경로), `tiny_nucleotide_db.fasta`/`tiny_protein_db.faa`(BLAST용)

`tests/integration/test_fixtures_import_all.py`에서 전체 import를 자동 검증한다.
