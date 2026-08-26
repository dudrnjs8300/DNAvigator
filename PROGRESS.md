# PROGRESS

이 문서는 milestone 체크리스트와 각 phase의 gate 통과 여부, 다음 session이 이어갈 정확한 지점을 기록한다. 새 session은 `docs/PRODUCT_SPEC.md`, 이 문서, `git log`, 실패 테스트를 먼저 읽고 이어간다.

## 현재 상태 요약 (2026-08-26, 2차 업데이트)

- Phase 0, Phase 1 완료. **사용자 피드백으로 Phase 3(genome visualization)과 Phase 5/6(BLAST)의 핵심을 Phase 2보다 먼저 앞당겨 구현함** — 최초 구현이 "sequence 목록 조회기"에 가깝고 Geneious 스타일의 실제 시각화 워크벤치가 아니라는 지적을 받아, 중앙 화면과 상호작용을 전면 재설계했다. 자세한 내용은 "Phase 3/BLAST 조기 구현" 절 참고.
- 전체 테스트: **112 passed** (`pytest tests -q`, `QT_QPA_PLATFORM=offscreen`). UI 테스트 7개 중 4개가 실제 마우스 드래그/클릭/줌/BLAST 워크플로를 검증한다(`tests/ui/test_genome_visualization_workflow.py`).
- `ruff format --check`, `ruff check`, `mypy src/genome_workbench` 모두 clean.
- Windows onedir 빌드(`dist/GenomeWorkbench/GenomeWorkbench.exe`) 새 코드 포함해 재빌드 및 재검증 완료: `--self-test`, `--smoke-test` 모두 exit 0.
- 개발 환경 Python은 3.14.6 (3.12 미설치, D-001 참고). `requires-python`은 `>=3.12` 유지.

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

## Phase 2 — GenBank/GFF3와 복합 feature (다음 작업)

### 아직 안 한 것

- [ ] multi-record GenBank의 record-level metadata(annotations_json에 organism/taxonomy/references 등) 보존 — 현재는 최소 필드만 저장
- [ ] GFF3 parser/writer (`infrastructure/formats/gff3_adapter.py` 미생성)
- [ ] embedded/separate FASTA pairing, seqid mapping wizard
- [ ] Parent/child graph (feature_relationship 테이블은 이미 존재하나 GFF3 adapter에서 실제로 채우지 않음)
- [ ] fuzzy location의 GFF3 표현, validation framework 확장 (현재 `domain/validation.py`는 좌표범위/CDS translation만 검사)
- [ ] compound_fuzzy.gbk, annotated_embedded.gff3 등 나머지 fixture 생성 (현재 fixture는 `simple_linear.fasta`만 존재 — 16.2절 목록의 나머지 11개 fixture 아직 없음)
- [ ] `docs/FORMAT_SUPPORT.md` compatibility matrix 채우기

### 다음 session 시작 지점

1. `tests/fixtures/`에 spec 16.2 목록의 나머지 fixture를 합성 데이터로 생성 (`multi_contig.fasta`, `protein_set.faa`, `annotated_linear.gbk`, `circular_origin.gbk`, `compound_fuzzy.gbk`, `annotated_embedded.gff3`, `annotation_only.gff3`+`matching.fna`, `invalid_coordinates.gff3`, `duplicate_ids.fasta`, 한글 경로 fixture, BLAST용 tiny FASTA 2종).
2. `src/genome_workbench/infrastructure/formats/gff3_adapter.py` 신규 구현. 좌표 변환은 `domain/coordinates.py`, part 순서/strand 규칙은 `domain/locations.py`(D-002 규칙)를 그대로 재사용 — GFF3의 discontinuous feature(같은 ID를 가진 여러 줄)도 Biopython GenBank와 동일한 order_index 규칙을 따라야 semantic_compare가 일관되게 동작함.
3. `Feature.parent_ids`/`child_ids`를 GFF3 adapter에서 실제로 채우고, `sqlite_repository.py`의 `feature_relationship` 테이블 round-trip을 테스트로 검증.
4. Phase 2 gate: 제공 fixture 전체 import, GenBank/GFF3 semantic round-trip, negative strand/joined CDS/phase 테스트 통과.

## Phase 3–8

미착수. `docs/PRODUCT_SPEC.md` 17장 원문 참고. 각 phase 착수 시 이 파일에 체크리스트를 추가할 것.

## 알려진 리스크 / 재검증 필요 항목

- `docs/DECISIONS.md` D-005: PyInstaller windowed 빌드에서 CLI 플래그 사용 시 `AttachConsole`로 부모 콘솔에 출력하는 경로는 실제 대화형 터미널(cmd.exe/PowerShell)과 GitHub Actions runner에서 아직 재검증하지 못했다(이 개발 sandbox 자체에 진짜 콘솔이 없어 확인 불가). 대신 모든 CLI 출력은 `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json`에도 항상 기록하도록 만들어 콘솔 여부와 무관하게 검증 가능하게 했다.
- `.github/workflows/*.yml`은 로컬에서 동일 명령을 수동 실행해 통과를 확인했을 뿐, 실제 GitHub Actions에서 실행된 적은 없다(원격 저장소 push 권한/승인 필요).
