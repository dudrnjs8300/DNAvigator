# Release Test Report

작성일: 2026-08-26
버전: 0.1.0
검증 환경: 개발 머신(Windows 10.0.19045 x64, Python 3.14.6), 자동화 테스트 스위트, 실제 PyInstaller onedir 빌드, 실제 NCBI BLAST+ 2.17.0(win64) 설치
검증하지 못한 것은 "검증하지 못함"이라고 명시한다 — 통과로 보고하지 않는다.

## 요약

- 자동화 테스트: **192 passed**, 0 failed (`pytest tests -q`, `QT_QPA_PLATFORM=offscreen`; 실제 BLAST+ 테스트 2건 포함, BLAST+ 미설치 환경에서는 자동 skip)
- `ruff format --check`, `ruff check`, `mypy src/genome_workbench`: 모두 clean
- Windows 실행파일(onedir) 빌드 성공, `--self-test`/`--smoke-test` exit code 0
- Portable ZIP: 별도 임시 경로 및 한글/공백 경로로 압축 해제 후 `--self-test` exit code 0 확인
- Installer: Inno Setup 6로 컴파일 성공, silent 설치(관리자 권한 불필요) → `--self-test`/`--smoke-test` → Start Menu 바로가기 확인 → silent 제거까지 이 개발 머신에서 검증. **완전히 별도의 clean Windows 사용자 계정/VM에서의 검증은 아직 하지 못함** (AT-10 참고)
- 실제 NCBI BLAST+ 2.17.0(win64) 바이너리: 공식 NCBI FTP에서 설치(MD5 확인)해 blastn/blastp/database 생성/좌표 매핑/annotation 적용까지 실제로 검증(아래 AT-06/AT-07 참고). 대역(mock) 실행파일 기반 테스트도 회귀 검증용으로 계속 유지.

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

**통과 — 실제 BLAST+로 검증됨.** `tests/integration/test_blast_pipeline.py::test_create_database_with_mock_makeblastdb`가 안전하지 않은 ID(`|` 포함) → safe ID 매핑 → manifest 생성 → `blastdbcmd -info` 검증까지의 코드 경로를 대역 실행파일로 계속 확인한다. 여기에 더해 `tests/integration/test_blast_real_installation.py::test_real_blastn_self_hit_and_apply_as_annotation`이 **실제 NCBI BLAST+ 2.17.0**(공식 NCBI FTP에서 설치, MD5 확인됨)으로 동일한 시나리오를 재현한다: 실제 `makeblastdb`로 `simple_linear.fasta`에서 database 생성 → 실제 `blastn`으로 자기 자신의 300bp 조각 검색(identity/coverage 100%) → genome 좌표로 매핑 → annotation 적용까지 전부 실제 바이너리로 통과.

## AT-07 protein BLAST annotation

**통과 — blastn UI e2e + blastp 실제 바이너리 검증.** `tests/ui/test_genome_visualization_workflow.py::test_blast_run_and_apply_hit_as_annotation_end_to_end`가 UI 계층에서 선택 영역 BLAST 실행 → hit 선택 → `product`는 제외하고 `note`만 선택해 적용 → 적용 후 origin locus_tag/protein_id가 복사되지 않음(체크박스 기본값이 그렇게 설계됨)까지 검증한다(blastn 경로). 여기에 더해 `tests/integration/test_blast_real_installation.py::test_real_blastp_self_hit`이 **실제 blastp**로 protein database 생성 → protein 검색 → 정확한 top hit(자기 자신)까지 서비스 계층에서 검증한다. 남은 gap: UI 계층(dispatch/dialog)에서 blastp를 직접 구동하는 자동 테스트는 여전히 blastn 경로만 있다 — program 값과 무관하게 동일한 UI 코드 경로를 타므로 위험은 낮다고 판단하나, 완전히 동일한 조합의 UI 자동 테스트는 아니다.

## AT-08 cancel and failure

**통과.** BLAST 실행 실패(예: 잘못된 database 경로, 실행파일 없음)는 `CallableWorker.failed` 신호 → `QMessageBox.critical`로 안전하게 처리되며 project가 손상되지 않는다. **Cancel UI를 새로 구현했다**: BLAST 패널의 "Cancel Job" 버튼이 `threading.Event`를 서비스 계층까지 전달하고, `infrastructure/blast/runner.py`가 `subprocess.run`(한 번 호출하면 끝날 때까지 끊을 수 없음) 대신 `subprocess.Popen`을 0.2초 간격으로 폴링하는 방식으로 바뀌어 취소 요청 시 실제 프로세스를 즉시 `kill()`한다. `tests/unit/test_blast_runner_cancel.py`가 실제 자식 프로세스(30초 sleep)를 spawn해 취소가 5초 이내(대부분 1초 이내)로 실제로 죽이는지 확인하고, `tests/ui/test_callable_worker_cancel.py`가 worker↔UI 배선을 확인한다. 취소된 job은 에러 대화상자 대신 로그에 기록된다. 부수적으로, 실행 중 새 BLAST job을 중복 시작하는 것도 이제 막힌다(이전에는 막지 않았음).

## AT-09 atomic export

**통과.** `tests/unit/test_atomic_write.py` 5건: 기존 유효 파일이 있는 상태에서 write 콜백이 강제로 실패했을 때 destination이 byte-identical하게 보존됨, temp 파일이 남지 않음, 성공 시에는 정상 교체됨, 상위 디렉터리 자동 생성을 확인.

## AT-10 Windows clean-machine

**부분 검증 — installer는 이 개발 머신에서 실제 설치/제거 검증됨, 완전히 별도의 clean 계정/VM은 아직 없음.** 이번 세션에서 다음을 실제로 수행했다:
- `iscc installer\genome_workbench.iss`로 installer(`GenomeWorkbench-0.1.0-win-x64-setup.exe`) 컴파일 성공.
- `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LANG=english`로 silent 설치 — `PrivilegesRequired=lowest` 설정대로 관리자 권한 없이 `%LOCALAPPDATA%\Programs\GenomeWorkbench`에 설치됨.
- 설치된 실행파일의 `--self-test`/`--smoke-test` 모두 exit code 0, Start Menu 바로가기(`GenomeWorkbench.lnk`) 생성 확인.
- `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`로 silent 제거 — 설치 디렉터리와 바로가기가 깨끗하게 제거됨을 확인(사용자 데이터는 애초에 설치 디렉터리 밖에 있어 영향 없음).
- (참고) 언어를 2개 이상 등록하면 `/VERYSILENT`만으로는 언어 선택 대화상자가 떠서 자동화 설치가 멈춘다 — `/LANG=`을 함께 지정해야 한다. 대화형(GUI) 설치에서는 해당되지 않는 제약이다.
- `--self-test`의 `blast_executable` 항목은 실제 탐지를 하지 않는 정적 안내 필드이며 `optional: true`로 표시되어 core 실패를 유발하지 않는다 — 이는 실제 NCBI BLAST+ 설치 여부와 무관하게(이 머신에는 이후 실제로 BLAST+를 설치했다) 동일하게 동작함을 확인.
- Portable ZIP을 완전히 다른 임시 경로(및 한글/공백 경로)에 압축 해제해 `--self-test`를 확인 — "이 실행파일 자체가 별도 Python 설치 없이 독립 실행됨"도 검증됨.

여전히 남은 것: **완전히 새로운 Windows 사용자 계정 또는 clean VM**에서의 검증(이 개발 머신은 Python/개발 도구가 이미 설치된 환경이라, "이 머신에 아무것도 없어도 동작하는가"를 완벽히 대체하지 못한다), 그리고 BLAST Setup Wizard를 통한 실제 BLAST+ 인식 노출 확인.

## 결론

P0 Definition of Done(spec 18절) 대부분이 자동화 테스트와 실제 빌드로 뒷받침되며, 이번 갱신으로 installer의 설치/실행/제거, BLAST 파이프라인(blastn/blastp) 실제 바이너리 검증, BLAST job 취소 UI까지 모두 이 개발 머신에서 실증되었다. 다음은 여전히 미완/미검증 상태이며 "완성"이라고 보고하지 않는다:
- 완전히 별도의 clean Windows 사용자 계정/VM에서의 installer 설치 검증
- blastp 경로의 UI 계층(dispatch/dialog) 전용 자동 테스트(서비스 계층은 실제 바이너리로 검증됨)
- blastx/tblastn(번역 검색) frame 좌표 매핑의 실제 바이너리 검증(blastn/blastp만 검증됨)
