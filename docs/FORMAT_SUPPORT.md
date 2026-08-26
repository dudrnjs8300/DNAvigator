# 형식 지원 현황 (Phase 1 기준)

GFF3는 아직 구현되지 않았다(Phase 2). 이 문서는 실제 코드가 지원하는 범위만 기록하며, 지원하지
않는 것을 지원한다고 표시하지 않는다(`docs/PRODUCT_SPEC.md` 25.4 금지사항).

## 입력 형식

| 형식 | 확장자 | 상태 | 비고 |
|---|---|---|---|
| Nucleotide/Protein FASTA | `.fasta`, `.fa`, `.fna`, `.ffn`, `.fnn`, `.fas`, `.fsa`, `.faa` 및 `.gz` | 지원 | `infrastructure/formats/fasta_adapter.py`. Molecule type은 alphabet 기반 추정(`guess_molecule_type`), IUPAC ambiguous nucleotide 허용. |
| GenBank | `.gb`, `.gbk`, `.genbank`, `.gbff` 및 `.gz` | 부분 지원 | `infrastructure/formats/genbank_adapter.py`. Multi-record import 가능. Compound(join)/reverse-strand/fuzzy(Before/After) location 지원. **Record-level metadata(organism, taxonomy, references, comments)는 아직 domain model에 매핑하지 않음.** |
| GFF3 | `.gff`, `.gff3` | **미지원** | Phase 2 예정. |
| Generic FASTA (확장자 무관) | — | 지원 | `format_sniffer.py`가 magic bytes/첫 줄로 판별. |

## 출력 형식

| 형식 | 상태 | 비고 |
|---|---|---|
| GenBank | 지원 | `write_genbank`. Export 전 temp file에 쓴 뒤 reimport하여 semantic diff를 검사하고, 오류가 없을 때만 atomic replace한다(`application/export_service.py`). |
| GFF3 | 미지원 | Phase 2. |
| Nucleotide/Protein FASTA, FFN, feature table CSV/TSV | 미지원 | Phase 7 예정. |

## 보존되는 것 (검증됨, `tests/integration/test_genbank_adapter.py` 참고)

- Sequence content, molecule type(DNA/RNA/protein), topology(linear/circular)
- Feature type, strand, simple/join location, order_index
- Qualifier: key 순서, multi-value 순서, flag qualifier(빈 값), 알 수 없는 custom qualifier
- Compound reverse-strand feature의 생물학적 추출 서열/translation (D-002 규칙 참고 — `docs/DECISIONS.md`)
- Fuzzy position(`<`/`>`, GenBank `BeforePosition`/`AfterPosition`)

## 알려진 손실/미보존 (현재 시점)

- GenBank record-level annotation(organism, taxonomy, DBLINK, REFERENCE, COMMENT 등) — Phase 2에서 `annotations_json`에 매핑 예정
- Parent/child(GFF3 관계) — GenBank에는 해당 개념이 없으므로 N/A, GFF3 adapter 구현 시 별도 검증
- `/translation`과 재계산 translation의 불일치 감지는 validation issue로 나타나지만(9.3절), export 시 자동 비교 리포트는 아직 없음(Phase 2/7)

## 테스트된 fixture

- `tests/fixtures/simple_linear.fasta` (1000 bp 합성 DNA, 무주석)
- 나머지 spec 16.2 fixture 목록(multi_contig, protein_set, annotated_linear, circular_origin,
  compound_fuzzy, GFF3 관련, invalid_coordinates, duplicate_ids, 한글 경로, BLAST용 tiny FASTA)은
  아직 생성되지 않음 — `PROGRESS.md`의 "다음 session 시작 지점" 참고.
