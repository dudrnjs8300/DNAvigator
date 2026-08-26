# PROGRESS

이 문서는 milestone 체크리스트와 각 phase의 gate 통과 여부, 다음 session이 이어갈 정확한 지점을 기록한다. 새 session은 `docs/PRODUCT_SPEC.md`, 이 문서, `git log`, 실패 테스트를 먼저 읽고 이어간다.

## 현재 상태 요약 (2026-08-26, 7차/최종 업데이트)

- Phase 0~8 전부 완료. 이전 업데이트에서 "이 sandbox에서 할 수 없다"고 적었던 5개 항목을 이번 세션에서 전부 완료했다: Inno Setup installer 컴파일+설치/제거 검증, 실제 NCBI BLAST+ 바이너리 검증, BLAST job 취소 UI, **그리고 GitHub 원격 저장소 push + 실제 GitHub Actions 실행까지.** 남은 것은 순수하게 "이 개발 머신 자체로는 대체할 수 없는 것"(완전히 별도의 clean Windows 계정/VM에서의 **installer** 설치 검증)뿐이다 — 아래 참고.
- **GitHub**: 사용자 승인 하에 `https://github.com/dudrnjs8300/genome-workbench`(public) 생성, 전체 히스토리 push, `test.yml`(품질 게이트) + `windows-release.yml`(실제 빌드+패키징+clean 러너 exe 검증) 둘 다 실제로 실행해 통과 확인. 이 과정에서 (1) `test.yml`이 `main`만 감시해 `master` push에 전혀 반응하지 않던 설정 버그, (2) `windows-release.yml`이 pwsh에서 exe를 직접 호출할 때 stdout/stderr가 캡처되지 않아 원인 불명으로 실패하던 문제(→ `Start-Process` 명시적 리다이렉트로 해결)를 발견해 고쳤다.
- 전체 테스트: **192 passed** (`pytest tests -q`, `QT_QPA_PLATFORM=offscreen`; 실제 BLAST+ 테스트 2건 포함하며 BLAST+ 미설치 환경에서는 자동 skip).
- `ruff format --check`, `ruff check`, `mypy src/genome_workbench` 모두 clean.
- Portable ZIP + **Installer(.exe)** 둘 다 빌드/검증 완료: `release/GenomeWorkbench-0.1.0-win-x64-portable.zip`, `release/GenomeWorkbench-0.1.0-win-x64-setup.exe` (+ 각각 `.sha256`). Installer는 silent 설치(관리자 권한 불필요, `%LOCALAPPDATA%\Programs`) → `--self-test`/`--smoke-test` → Start Menu 바로가기 확인 → silent 제거까지 이 머신에서 실제로 검증됨.
- **실제 NCBI BLAST+ 2.17.0(win64)**을 공식 FTP에서 설치(MD5 확인)해 blastn/blastp/database 생성/좌표 매핑/annotation 적용을 전부 실제 바이너리로 검증(`tests/integration/test_blast_real_installation.py`, BLAST+ 없는 환경에서는 자동 skip). 이 과정에서 `detector.py`의 버전 하드코딩 버그(2.16.0+만 인식)를 발견해 고쳤다.
- 개발 환경 Python은 3.14.6 (3.12 미설치, D-001 참고). `requires-python`은 `>=3.12` 유지.

## 이번 세션 추가 작업 (2026-08-26, 사용자가 4개 기능 확인 요청 후)

사용자가 "① 유전자 방향 표시, ② feature hover 시 정보 툴팁, ③ 원형 조립 여부에 따른 원형/선형 표시, ④ 유전자 이름/정보 검색"이 구현되어 있는지 확인해달라고 요청했다. 코드를 직접 확인한 결과 ①②는 이미 구현되어 있었고(`GenomeCanvas`/`CircularGenomeCanvas`의 strand arrow + tooltip), ③④는 없었다:

- [x] **③ topology 기반 Circular Map tab 제어**: `MainWindow._apply_topology_tab_state`/`_select_default_tab_for_current_record` 추가. Circular Map tab은 현재 record의 topology가 실제로 CIRCULAR일 때만 활성화되고 자동으로 기본 선택된다. Linear record에서는 비활성화되고(원점이 없는 분자를 원형으로 그릴 근거가 없으므로) Genome Map으로 자동 대체된다.
- [x] **④ Find Feature(Ctrl+F)**: `ui/dialogs/find_feature_dialog.py` 신규 — project 전체 record를 대상으로 gene/locus_tag/product/note/모든 qualifier 값을 부분 일치 검색, 결과 더블클릭/Enter로 해당 record 전환 + zoom-to-feature + Inspector 동기화.
- [x] UI 테스트 2건 추가(`test_circular_topology_drives_which_map_tab_is_available`, `test_find_feature_by_gene_name_navigates_to_match`), `docs/USER_GUIDE_KO.md`에 섹션 추가.

이후 사용자가 이전에 기록해둔 우선순위(Inno Setup → 실제 BLAST+ → BLAST cancel UI) 그대로 이어서 진행했다(사용자 승인 하에 winget으로 Inno Setup 설치, 공식 NCBI FTP에서 BLAST+ 설치):

- [x] **Inno Setup installer**: winget으로 Inno Setup 6 설치 → `installer/genome_workbench.iss` 컴파일 → silent 설치/실행/제거 전체 사이클 검증. 언어 2개 등록 시 `/VERYSILENT`만으로는 언어 선택 대화상자가 떠서 자동화 설치가 멈추는 것을 발견 — `/LANG=`을 함께 지정해야 함을 확인하고 스크립트 주석에 기록.
- [x] **실제 BLAST+ 검증**: 위 요약 참고. `tests/integration/test_blast_real_installation.py` 추가.
- [x] **BLAST job 취소 UI**: `infrastructure/blast/runner.py`를 `subprocess.run`(끊을 수 없음) 대신 `subprocess.Popen` + 0.2초 폴링으로 교체해 `threading.Event`로 실제 취소 가능하게 만들고, `CallableWorker.with_cancel_support()` + `BlastPanel`의 "Cancel Job" 버튼으로 연결. `tests/unit/test_blast_runner_cancel.py`(실제 30초 sleep 자식 프로세스를 5초 이내에 죽이는지 확인), `tests/ui/test_callable_worker_cancel.py` 추가.
- [x] 매 단계마다 dist 재빌드 → portable ZIP/installer 재생성 → self-test/smoke-test/설치-제거 재검증 → 커밋을 반복해, 최종 산출물이 모든 변경사항을 반영하고 있음을 확인했다.

## Phase 8 — Windows release와 문서 (거의 완료, 2026-08-26)

- [x] `docs/USER_GUIDE_KO.md`, `docs/BLAST_SETUP.md` — 실제 구현된 화면/메뉴만 기준으로 작성.
- [x] `docs/RELEASE_TEST_REPORT.md` — AT-01~AT-10 결과를 정직하게 기록(통과/부분통과/미검증을 명확히 구분).
- [x] `release/` 산출물: portable ZIP + SHA-256 checksum + THIRD_PARTY_NOTICES.md + RELEASE_NOTES.md. 압축 해제 후 격리된 경로(및 한글/공백 경로)에서 `--self-test` 재검증함.
- [x] `installer/genome_workbench.iss` (Inno Setup 스크립트) 작성 — **컴파일하지 못함** (이 환경에 Inno Setup Compiler 없음). 실제 설치본을 만들려면 `iscc installer\genome_workbench.iss` 실행 필요.
- [ ] 실제 GitHub Actions에서 `.github/workflows/*.yml` 실행 검증 — 원격 저장소 push 및 사용자 승인 필요, 이 세션에서는 로컬 수동 실행으로만 동일 절차를 확인함.
- [ ] 실제 NCBI BLAST+ 바이너리로 BLAST 파이프라인 재검증 — 이 환경에 BLAST+ 미설치.
- [ ] Clean Windows VM에서의 installer 설치/실행/제거 검증 — 미실시.

## Phase 7 — export 완성, sequence operations (완료, 2026-08-26)

- [x] `infrastructure/formats/export_formats.py`: nucleotide FASTA, protein FASTA(record 직접 export / CDS translation export 두 가지), FFN(CDS 생물학적 서열), feature table CSV — 전부 `ExportService`를 통해 atomic write로 노출되고 File 메뉴에 연결됨.
- [x] `SequenceOperationsService.extract_as_new_record`/`reverse_complement_as_new_record` (spec 10.1 non-destructive operations) — canvas 우클릭 메뉴의 "Extract Selection as New Record.../Reverse Complement Whole Record as New Record..."로 연결, 새 record는 project에 저장되지만 원본은 변경되지 않음.
- **아직 안 한 것**: P1 base editor(substitution/insertion/deletion, 명세 10.2 — 의도적으로 P1로 유예), 성능 벤치마크(5.5Mb/6000 feature), malformed/adversarial input 전용 테스트 확대, 8시간 soak test.

## Phase 2 — GenBank/GFF3와 복합 feature (완료, 2026-08-26)

- [x] `infrastructure/formats/gff3_adapter.py`: 9-column parser/writer, directive(`##sequence-region`/`##species`/`##genome-build` 등 보존), embedded/separate FASTA, percent-escaping, discontinuous feature(같은 ID) → compound location, Parent/child 관계, cycle 검출. Reverse-strand discontinuous feature의 order_index 규칙은 D-002와 동일하게 `order_parts_for_strand`를 재사용(문서화: 모듈 docstring + D-002).
- [x] `##gff-version 3` 헤더가 없는 파일은 GFF2/기타로 판단해 조용히 오해석하지 않고 명시적 오류를 낸다(spec 6.5 요구사항).
- [x] GenBank record-level metadata(organism, taxonomy, source, keywords, accessions, comment, references) `annotations_json`에 보존 — import/export round-trip 테스트 통과.
- [x] `ImportService.import_gff3`/`ExportService.export_gff3` (embed_fasta 옵션, separate FASTA pairing, semantic round-trip 검증), MainWindow File 메뉴에 연결(Import GFF3/Export GFF3, 얽힌 FASTA 선택 프롬프트 포함).
- [x] `semantic_compare.py`에 parent/child relationship 비교 추가(position 기반 매칭, ID는 재수입 시 바뀌므로).
- [x] spec 16.2 fixture 전부 생성(`multi_contig.fasta`, `protein_set.faa`, `annotated_linear.gbk`, `circular_origin.gbk`, `compound_fuzzy.gbk`, `annotated_embedded.gff3`, `annotation_only.gff3`+`matching.fna`, `invalid_coordinates.gff3`, `duplicate_ids.fasta`, 한글 경로 fixture, BLAST용 tiny FASTA 2종) — `scratch/generate_fixtures.py`(gitignore됨, 재실행 가능)로 생성. `tests/integration/test_fixtures_import_all.py`가 전부 import 검증.
- **Gate 통과**: 제공 fixture 전체 import(26개 테스트), GenBank/GFF3 semantic round-trip, negative strand/joined CDS/phase 테스트 통과.

### 다음 session 시작 지점 (Phase 8만 남음)

1. Windows installer(Inno Setup 스크립트, `installer/genome_workbench.iss`는 아직 빈 디렉터리).
2. `docs/USER_GUIDE_KO.md`, `docs/BLAST_SETUP.md` 실제 작성(현재 화면 기준 스크린샷 필요).
3. 실제 GitHub Actions에서 `.github/workflows/*.yml` 실행 검증(원격 push 필요, 사용자 승인 필요).
4. PyInstaller 최종 재빌드 + `--self-test`/`--smoke-test` 재검증, portable ZIP/checksum 생성.
5. `docs/RELEASE_TEST_REPORT.md`에 AT-01~AT-10 acceptance test 결과 기록.

## Phase 0 — 저장소, 품질 기준, 실행 skeleton

- [x] `pyproject.toml`, venv, dev dependency 설치 (PySide6 6.11.2, biopython 1.88, pytest 9.x, ruff, mypy, hypothesis, pytest-qt)
- [x] `src/genome_workbench` 패키지 skeleton (domain/application/infrastructure/ui 레이어 분리)
- [x] PySide6 main window + dock/tab shell (`ui/main_window.py`)
- [x] logging (`infrastructure/logging_setup.py`), 사용자 디렉터리 (`infrastructure/filesystem/paths.py`)
- [x] pytest/Ruff/mypy 설정 (`pyproject.toml`)
- [x] PowerShell 스크립트: `scripts/bootstrap_dev.ps1`, `scripts/run_checks.ps1`, `scripts/build_windows.ps1`
- [x] CI workflow: `.github/workflows/test.yml` (windows-latest, 아직 실제 GitHub Actions 실행으로 검증되지는 않음 — 로컬에서 동일 절차를 수동 실행해 통과 확인)
- [x] `version.py` (APP_VERSION=0.1.0, SCHEMA_VERSION=1)
- **Gate**: source run 성공(✓ `python -m genome_workbench --version` 등), empty UI smoke test(✓ `tests/ui/test_main_window_smoke.py::test_main_window_launches_empty`), lint/type/unit test 성공(✓), Windows executable 생성 및 launch(✓ PyInstaller onedir 빌드 후 `--self-test`/`--smoke-test` 실제 실행 확인, GUI 모드도 offscreen platform으로 5초간 정상 구동 후 timeout kill로 크래시 없음 확인).

## Phase 1 — FASTA → 수동 annotation → project → GenBank 수직 슬라이스

- [x] canonical record/feature/location 모델 (`domain/models.py`, `domain/locations.py`, `domain/qualifiers.py`)
- [x] 좌표 변환 + property-based 테스트 (`domain/coordinates.py`, `tests/unit/test_coordinates.py`)
- [x] FASTA sniffer/import (`infrastructure/formats/format_sniffer.py`, `fasta_adapter.py`)
- [x] GenBank import/export adapter (`genbank_adapter.py`) — Phase 2 예정이었으나 AT-01 round-trip 검증을 위해 Phase 1에서 앞당겨 구현함(단, multi-record 전체 기능·GFF3는 여전히 Phase 2)
- [x] semantic round-trip 비교기 (`semantic_compare.py`)
- [x] project SQLite create/save/open, schema v1 (`infrastructure/persistence/`)
- [x] project explorer, feature table, inspector, 최소 sequence view (`ui/docks/`, `ui/views/`)
- [x] interval selection + manual simple feature 생성 dialog (`ui/dialogs/add_feature_dialog.py`)
- [x] undo/redo (pure-Python `application/commands.py::UndoStack`, Qt 비의존)
- [x] export → reimport semantic check, atomic write (`application/export_service.py`)
- [x] CLI `--self-test`/`--smoke-test`/`--diagnostics`/`--version` (`__main__.py`, `diagnostics.py`)
- **Gate**: 시나리오 A가 자동 테스트로 완주됨(`tests/integration/test_scenario_a_end_to_end.py`), 앱 재시작(프로젝트 close/reopen) 후 데이터 유지 확인(같은 테스트 내), UI를 통한 동일 흐름도 검증됨(`tests/ui/test_main_window_smoke.py::test_new_project_import_fasta_add_feature_save_reopen`).

### 중요 설계 판단 (자세한 내용은 `docs/DECISIONS.md`)

- **D-002가 가장 중요**: compound reverse-strand location 추출은 "전체를 이어붙인 뒤 reverse-complement"가 아니라 "각 part를 개별적으로 strand 보정한 뒤 order_index 순서로 이어붙이기"다. Biopython의 실제 동작을 직접 검증해서 확정함. 이후 GFF3 adapter(Phase 2)나 BLAST 좌표 매핑(Phase 6)에서 동일 규칙을 반드시 재사용할 것 — 별도로 재유도하지 말 것.
- Feature.strand는 단일 값(D-004): part별 strand가 다른 경우는 P0 범위 밖.

## Phase 3 / BLAST 조기 구현 (사용자 피드백 반영, 2026-08-26)

사용자가 초기 UI를 검토한 뒤 "sequence 목록 조회기 수준이며 Geneious 스타일의 실제 genome visualization이 아니다"라고 지적했다. 이에 따라 Phase 2(GFF3)보다 Phase 3(시각화)와 Phase 5/6(BLAST)의 핵심 기능을 먼저 구현했다. 계획 변경이지 축소가 아니다 — 아래는 실제로 완성되어 테스트로 검증된 것만 기록한다.

### 완성됨

- [x] `ui/rendering/viewport_transform.py`: genome↔pixel 좌표 변환, LOD 단계(overview/gene/feature/base) 계산, zoom/pan/fit 로직. Qt 비의존, 순수 Python 단위 테스트 완비.
- [x] `ui/rendering/feature_interval_index.py`: sorted-start + bisect 기반 viewport 조회 (spec 8.3 권장 방식).
- [x] `ui/views/genome_canvas.py` (`GenomeCanvas`): 단일 연속 확대 가능한 QPainter 기반 canvas. LOD별로 density bar → 색상 strand-화살표 → label → 염기 문자(top/complement/CDS translation overlay)까지 하나의 화면에서 전환됨. Mouse wheel(zoom, anchor 고정), Shift+wheel(pan), drag-select, feature click/hover(tooltip)/double-click(zoom-to-feature), feature 경계 drag-resize(단일 part feature만), 우클릭 → context menu 신호.
- [x] `ui/views/circular_genome_canvas.py`: strand별 inner/outer ring, feature arc, origin marker, click/hover/double-click.
- [x] `ui/widgets/minimap.py`: 전체 genome 개요 strip + viewport box, 클릭/드래그로 이동.
- [x] `ui/views/genome_map_page.py`: canvas+minimap+zoom 툴바를 묶은 "Genome Map" 탭 — **이것이 이제 프로그램의 중앙 화면**이다. 기존 text 기반 "Sequence"/"Overview" 탭은 완전히 폐기했다.
- [x] `ui/main_window.py` 전면 재작성: 중앙 탭이 Genome Map / Circular Map / Feature Table 세 개뿐이다. Feature click/table row click/circular click이 canvas·table·inspector 3-way로 동기화된다. 우클릭 컨텍스트 메뉴(Add Annotation/Run BLAST/Copy Sequence/Copy Reverse Complement/Translate ±/Export Selection)가 실제 선택 영역에서 동작한다.
- [x] `ui/docks/inspector_dock.py`: 읽기 전용 텍스트에서 **편집 가능한 폼**으로 전면 교체 — type/strand/좌표/공통 qualifier를 직접 수정하고 Apply/Revert로 저장한다(값 변경 시 실시간 nucleotide/translation/validation preview).
- [x] `ui/docks/project_explorer_dock.py`: annotation 개수 컬럼 추가, 우클릭으로 topology(linear/circular) 변경(`ProjectService.set_record_topology`).
- [x] `application/sequence_operations_service.py`: copy/reverse-complement/translate/export-selection (spec 10.1 non-destructive operations).
- [x] **BLAST 실제 파이프라인** (Phase 5/6에서 앞당김): `domain/blast_models.py`(BlastProgram/Database/Hit/Hsp/SearchResult, HSP→genome 좌표 매핑 함수 `map_hsp_to_genome_location` — 역방향 query에서도 정확함을 4개 케이스로 단위 테스트함), `infrastructure/blast/`(detector/command_builder/runner/parser/database_manager — subprocess는 항상 argument list, Windows에서 CREATE_NO_WINDOW), `application/blast_service.py`(설치 탐지, DB 카탈로그 JSON 영속화, 검색 실행, hit→annotation 적용 시 Provenance 기록), `ui/docks/blast_panel.py` + `ui/dialogs/blast_setup_dialog.py`/`create_blast_database_dialog.py`/`apply_blast_hit_dialog.py`, `ui/workers/callable_worker.py`(QThread로 UI 블로킹 방지).
- [x] `tests/fixtures/fake_blast/*.bat`: 실제 NCBI BLAST+가 없는 환경에서 makeblastdb/blastdbcmd/blastn을 대신하는 가짜 실행파일. **진짜 subprocess 호출**로 command 구성/실행/파싱 전체 경로를 검증한다(spec 16.1 "mock BLAST executable interaction"). `tests/integration/test_blast_pipeline.py`.
- [x] `tests/ui/test_genome_visualization_workflow.py`: 실제 마우스 드래그로 선택 생성 → 컨텍스트 메뉴로 annotation 생성(dialog가 드래그 좌표로 미리 채워짐을 확인), feature 클릭/더블클릭 동기화, BLAST 실행→hit 선택→적용까지 GUI 코드 경로로 end-to-end 검증.

### 이번 재설계에서 발견/수정한 버그

- `QMenu.exec()`는 PySide6/Shiboken 바인딩 메서드라서 `monkeypatch.setattr(QMenu, "exec", ...)`가 조용히 무시되고 실제 모달이 떠서 headless 환경에서 영원히 멈춘다. `_on_canvas_context_menu`(메뉴 표시)와 `_dispatch_selection_action`(로직)을 분리해 테스트는 후자를 직접 호출하도록 리팩터링했다 — 프로덕션 동작은 동일하다.
- `BlastService`가 프로젝트와 무관하게 `%LOCALAPPDATA%/GenomeWorkbench/blast/catalog.json`을 전역으로 읽고 쓰는데, 테스트가 매번 실제 사용자 프로필을 오염시켰다. `BlastService(work_dir=...)`와 `MainWindow(blast_work_dir=...)`로 주입 가능하게 고쳐 테스트는 `tmp_path`를 쓰도록 했다(프로덕션 기본값은 기존과 동일하게 전역 카탈로그 — 여러 project에서 DB를 재사용하는 것은 의도된 설계).

### 아직 안 한 것 (이번 재설계 범위 밖)

- [ ] Circular map의 zoom/rotation (spec 7.3 "zoom/pan 또는 rotation" 중 rotation 미구현, click selection만 있음)
- [ ] Compound(join)/fuzzy location을 만드는 UI (여전히 단일 구간만 마우스로 생성 가능 — domain/adapter는 이미 지원하므로 Phase 4에서 UI만 추가하면 됨)
- [ ] BLAST DB의 project 귀속/삭제 시 정리, 여러 query(batch BLAST) 미지원
- [ ] GC content/skew track, feature drag로 여러 구간 join 편집

## 다음 session이 있다면 시작할 지점

P0 핵심 기능은 전부 구현·테스트되었다. 진짜로 남은 것은 이 개발 머신 자체의 한계로 여기서는 못 하는 한 가지뿐이다:

1. **완전히 별도의 clean Windows 사용자 계정 또는 VM**에서 **installer(.exe)** 설치/실행/제거 검증 (spec AT-10) — installer는 이 개발 머신에서 silent 설치/제거까지 실증되었고, 패키징된 exe 자체는 GitHub Actions의 진짜 clean `windows-latest` 러너에서도 검증되었지만(`https://github.com/dudrnjs8300/genome-workbench/actions/runs/32968044295`), installer(.exe)의 설치 과정 자체를 GitHub Actions는 다루지 않으므로 "완전히 별도의 사람/머신"에서의 installer 검증만 남아있다.

부가적으로 남은 더 작은 gap:
2. blastp(protein) 경로 UI 계층(dispatch/dialog) 전용 자동 테스트 — 서비스 계층은 실제 BLAST+로 검증됨(`test_blast_real_installation.py`), UI 계층은 blastn 경로만 있음. Program 값과 무관하게 동일한 코드 경로라 위험은 낮음.
3. blastx/tblastn(번역 검색) frame 좌표 매핑의 실제 바이너리 검증 — blastn/blastp만 실제 바이너리로 검증됨.
4. GitHub repo(`https://github.com/dudrnjs8300/genome-workbench`)가 아직 이 로컬 checkout과 완전히 동기화되지 않은 후속 커밋이 있는지 `git status`/`git log origin/master..master`로 항상 먼저 확인할 것 — 이제 원격이 존재하므로 앞으로는 세션마다 push 여부를 사용자에게 확인해야 한다(자동으로 push하지 않음).

## 알려진 리스크 / 재검증 필요 항목

- `docs/DECISIONS.md` D-005: PyInstaller windowed 빌드에서 CLI 플래그 사용 시 `AttachConsole`로 부모 콘솔에 출력하는 경로는 실제 대화형 터미널(cmd.exe/PowerShell)과 GitHub Actions runner에서 아직 재검증하지 못했다(이 개발 sandbox 자체에 진짜 콘솔이 없어 확인 불가). 대신 모든 CLI 출력은 `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json`에도 항상 기록하도록 만들어 콘솔 여부와 무관하게 검증 가능하게 했다.
- `.github/workflows/*.yml`은 로컬에서 동일 명령을 수동 실행해 통과를 확인했을 뿐, 실제 GitHub Actions에서 실행된 적은 없다(원격 저장소 push 권한/승인 필요).
