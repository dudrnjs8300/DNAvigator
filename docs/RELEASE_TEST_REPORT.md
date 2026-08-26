# Release Test Report

작성일: 2026-08-26
버전: 0.1.0
검증 환경: 개발 머신(Windows 10.0.19045 x64, Python 3.14.6), 자동화 테스트 스위트, 실제 PyInstaller onedir 빌드
검증하지 못한 것은 "검증하지 못함"이라고 명시한다 — 통과로 보고하지 않는다.

## 요약

- 자동화 테스트: **183 passed**, 0 failed (`pytest tests -q`, `QT_QPA_PLATFORM=offscreen`)
- `ruff format --check`, `ruff check`, `mypy src/genome_workbench`: 모두 clean
- Windows 실행파일(onedir) 빌드 성공, `--self-test`/`--smoke-test` exit code 0
- Portable ZIP: 별도 임시 경로 및 한글/공백 경로로 압축 해제 후 `--self-test` exit code 0 확인
- Installer: **빌드하지 못함** (Inno Setup Compiler가 이 환경에 없음)
- 실제 NCBI BLAST+ 바이너리: **사용하지 못함** (설치되어 있지 않음) — 대역(mock) 실행파일로 파이프라인 자체는 검증

## AT-01 FASTA manual annotation round-trip

**통과.** `tests/integration/test_scenario_a_end_to_end.py`(서비스 계층), `tests/ui/test_main_window_smoke.py::test_new_project_import_fasta_add_feature_save_reopen`(UI). FASTA import → CDS 101..900 생성(gene/product/note/transl_table) → project 저장·재오픈 → 값 유지 확인 → GenBank export → 새 project에서 재수입 → canonical sequence/feature/qualifier 동일 확인. Undo/redo도 별도로 검증됨.

## AT-02 reverse-strand CDS

**통과.** `tests/integration/test_genbank_adapter.py::test_at02_reverse_strand_cds_round_trip`. Reverse strand CDS 생성 → 표시된 nucleotide가 reverse complement인지, translation이 생물학적 방향으로 계산되는지, GBK export–reimport 후 checksum 동일한지 확인.

## AT-03 circular origin

**통과 (undo/redo는 별도 검증).** `tests/integration/test_fixtures_import_all.py::test_circular_origin_gbk_extraction_matches_source`로 origin-spanning CDS의 import/추출/생물학적 서열이 정확함을 확인. Linear/circular map에서의 시각적 선택은 `tests/ui/test_genome_visualization_workflow.py`의 feature 클릭 테스트로 (다른 fixture 대상) 검증되었으나, circular_origin.gbk를 UI로 직접 열어 클릭·좌표 수정·undo/redo까지 수행하는 단일 e2e 테스트는 없다 — 기능 자체(좌표 수정, undo/redo)는 다른 시나리오에서 검증되었고 circular origin 데이터 처리도 별도로 검증되었으므로 조합 리스크는 낮다고 판단하나, 완전히 동일한 조합의 자동 테스트는 아니다.

## AT-04 unknown qualifiers

**통과.** `tests/integration/test_genbank_adapter.py::test_unknown_qualifiers_preserved`. 알 수 없는 custom qualifier와 multi-value qualifier(`db_xref` 2개)가 export–reimport 후에도 순서와 값 그대로 보존됨을 확인.

## AT-05 GFF3 pairing

**통과.** `tests/integration/test_fixtures_import_all.py::test_annotation_only_gff3_pairs_with_matching_fna`, `test_unmatched_seqid_reported_when_no_sequence_available`, `tests/integration/test_gff3_service_integration.py`. Annotation-only GFF3 + 별도 FASTA 페어링, 불일치 seqid가 추정 적용 없이 issue로 보고됨을 확인. UI 흐름(불일치 시 FASTA 선택 프롬프트)은 `MainWindow._on_import_gff3`에 구현되어 있으나 이 특정 대화상자 흐름의 UI 자동 테스트는 없음(서비스 계층 로직은 검증됨).

## AT-06 custom nucleotide BLAST DB

**부분 통과 — 실제 BLAST+ 미사용.** `tests/integration/test_blast_pipeline.py::test_create_database_with_mock_makeblastdb`로 안전하지 않은 ID(`|` 포함) → safe ID 매핑 → manifest 생성 → `blastdbcmd -info` 검증까지의 전체 코드 경로를 대역 실행파일로 확인했다. Command 구성과 subprocess 호출은 실제 `makeblastdb.exe`/`blastdbcmd.exe` 이름과 인터페이스를 그대로 사용하도록 작성되어 있으나, **실제 NCBI BLAST+ 바이너리로 이 시나리오를 재현하지는 못했다.**

## AT-07 protein BLAST annotation

**부분 통과 — blastn 경로만 e2e 검증됨.** `tests/ui/test_genome_visualization_workflow.py::test_blast_run_and_apply_hit_as_annotation_end_to_end`가 선택 영역 BLAST 실행 → hit 선택 → `product`는 제외하고 `note`만 선택해 적용 → 적용 후 origin locus_tag/protein_id가 복사되지 않음(체크박스 기본값이 그렇게 설계됨)까지 검증한다. 다만 이 테스트는 **blastn(nucleotide)** 경로이며, blastp/protein CDS translation 조합으로 직접 실행한 자동 테스트는 없다. `suggest_program()`이 protein-vs-protein일 때 blastp를 올바르게 제안하는 것은 단위 테스트(`test_blast_models.py`)로 확인되었고 이후 파이프라인은 program 무관하게 동일한 코드 경로를 타므로 동작할 개연성은 높지만, protein 케이스 자체의 e2e 자동 테스트는 아직 없다.

## AT-08 cancel and failure

**부분 통과 — failure만 구현, cancel 미구현.** BLAST 실행 실패(예: 잘못된 database 경로, 실행파일 없음)는 `CallableWorker.failed` 신호 → `QMessageBox.critical`로 안전하게 처리되며 project가 손상되지 않는다(수동 확인 및 여러 단위 테스트의 예외 경로로 간접 확인). **그러나 실행 중인 job을 취소하는 UI(cancel 버튼)는 이번 릴리스에 구현되지 않았다.** `docs/KNOWN_LIMITATIONS.md`에 추가 필요.

## AT-09 atomic export

**통과.** `tests/unit/test_atomic_write.py` 5건: 기존 유효 파일이 있는 상태에서 write 콜백이 강제로 실패했을 때 destination이 byte-identical하게 보존됨, temp 파일이 남지 않음, 성공 시에는 정상 교체됨, 상위 디렉터리 자동 생성을 확인.

## AT-10 Windows clean-machine

**검증하지 못함.** Python과 BLAST가 설치되지 않은 별도의 clean Windows VM은 이 세션에서 준비하지 못했다. 대신 다음으로 대체 검증했다:
- 개발 머신 자체에는 BLAST+가 설치되어 있지 않으므로, "BLAST 미설치 상태에서 self-test가 core 실패로 처리되지 않고 `optional_tool_unavailable`로 분류됨"은 실제로 검증됨.
- Portable ZIP을 완전히 다른 임시 경로(및 한글/공백 경로)에 압축 해제해 `--self-test`/GUI 기동을 확인 — "이 실행파일 자체가 별도 Python 설치 없이 독립 실행됨"은 검증됨.
- 그러나 "완전히 새로운 Windows 사용자 계정/클린 VM에서의 installer 설치 → 실행 → BLAST Setup Wizard 노출 → 제거"는 수행하지 못했다.

## 결론

P0 Definition of Done(spec 18절) 대부분이 자동화 테스트와 실제 빌드로 뒷받침되지만, 다음은 아직 미완/미검증 상태이며 "완성"이라고 보고하지 않는다:
- 실제 NCBI BLAST+ 바이너리로의 재검증
- Job 취소(cancel) UI
- Installer 빌드 및 clean-machine 설치 검증
- protein(blastp) BLAST 경로의 전용 e2e 테스트
