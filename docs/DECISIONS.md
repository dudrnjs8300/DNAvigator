# 설계 판단 기록 (DECISIONS.md)

이 문서는 명세가 모호하거나 여러 구현이 가능한 지점에서 내려진 판단과 근거를 기록한다.

## D-001: 개발/테스트 Python 인터프리터로 3.14 사용

- **명세**: Python 3.12 계열을 기본으로 하되 "상호 호환되는 최신 patch 버전을 lock"하라고 명시.
- **현실**: 이 개발 환경에는 Python 3.14.6만 설치되어 있고 3.12는 없음. PySide6 6.11.2, biopython 1.88 모두 3.14용 wheel을 제공함을 `pip index versions`로 확인.
- **판단**: `pyproject.toml`의 `requires-python = ">=3.12"`는 유지하되(3.12+ 사용자 호환성 보장), 이 환경에서는 3.14로 개발·테스트한다. Windows 빌드/CI에서는 실제 사용 가능한 최신 안정 3.x를 사용하고 PyInstaller 호환성을 별도로 검증한다(Phase 8).
- **재검토 조건**: PyInstaller 또는 PySide6가 3.14에서 packaging 문제를 보이면 3.12/3.13으로 낮춘다.

## D-002: compound reverse-strand location 추출 알고리즘

- **명세 문구** (5.1.8): "CDS translation은 biological 5'→3' 순서의 ordered parts를 합친 뒤 strand를 적용하고 phase/codon_start를 고려한다." — 문언만 보면 "parts를 이어붙인 뒤 전체에 strand(reverse-complement)를 적용"으로 읽힌다.
- **검증**: `Bio.SeqFeature.CompoundLocation.extract()`를 직접 실행해 실제 동작을 확인함(코드는 세션 로그 참고). 결과: parts가 비연속(인트론/gap 존재)인 경우, "전체를 이어붙인 뒤 reverse-complement"와 "각 part를 개별적으로 strand 보정한 뒤 order_index 순서로 이어붙이기"는 서로 다른 결과를 낸다. 실제 GenBank 표준 및 Biopython 참조 구현은 후자(개별 보정 후 순서대로 결합)이며, 이는 실제 발표된 단백질 서열과 일치하는 유일한 해석이다.
- **판단**: `domain/locations.py::extract_sequence`는 "각 part를 order_index 순서로, strand=-1이면 개별적으로 reverse-complement한 뒤 그대로 이어붙인다"로 구현한다. 이에 따라 minus-strand compound feature는 order_index가 **descending genomic order**(생물학적 5'→3' 순서)여야 한다.
- **파급 효과**: `order_parts_for_strand()` 헬퍼를 추가해 "ascending genomic order로 주어진 parts"를 strand에 맞는 order_index로 변환한다. GenBank/GFF3 import adapter는 파일에 기록된 순서를 그대로 order_index로 보존한다(파일이 이미 올바른 생물학적 순서를 담고 있다고 신뢰). origin-spanning feature를 사용자가 UI에서 새로 만들 때도 이 헬퍼를 사용한다.
- **테스트**: `tests/unit/test_locations.py`에 Biopython 참조 동작과 대조하는 회귀 테스트를 추가함(`test_extract_matches_biopython_reference_for_spliced_minus_strand_gene`).

## D-003: SQLite qualifier 순서 보존 방식

- multi-value qualifier의 key 순서(첫 등장 순서)와 value 순서(입력 순서)를 모두 보존해야 함(5.3).
- **판단**: `qualifier` 테이블에 `seq_index`(feature 내 전역 단조 증가 정수)만 두고, key/value 쌍을 등장 순서대로 저장한다. 복원 시 `seq_index` 순으로 순회하며 `QualifierSet.add(key, value)`를 호출하면 key 최초 등장 순서와 value 순서가 자동으로 재구성된다. 별도의 key-order 테이블이 불필요해 스키마가 단순해진다.

## D-005: windowed(no-console) exe에서 CLI 진단 출력을 파일에도 항상 기록

- **문제**: `GenomeWorkbench.exe`는 GUI 실행 시 콘솔 창이 뜨면 안 되므로(`console=False`) PyInstaller onedir로 빌드했다. `--self-test` 등 CLI 플래그 사용 시에는 부모 콘솔에 `AttachConsole`로 붙어 출력하도록 구현했는데, 실제 대화형 터미널(cmd.exe/PowerShell)에서는 동작이 기대되지만 이 개발 sandbox 자체가 진짜 Win32 콘솔을 제공하지 않아(git bash의 mintty, 자동화 도구의 pipe 리다이렉션) `AttachConsole`이 실패하고 표준출력이 소실되는 현상을 발견했다.
- **판단**: 콘솔 유무에 의존하지 않는 검증 가능성을 확보하기 위해, `--version`/`--diagnostics`/`--self-test`/`--smoke-test`의 출력을 **항상** `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json` 파일에도 기록한다(표준출력 시도는 best-effort로 유지). 이는 spec 13.4의 "진단 결과 내보내기" 요구와도 부합한다.
- **검증**: 실제 빌드된 `dist/GenomeWorkbench/GenomeWorkbench.exe`에 대해 `--version`, `--self-test`, `--smoke-test`를 모두 실행해 exit code 0과 파일 출력을 직접 확인함(세션 로그 참고). `--self-test`는 Qt platform plugin 로드까지 frozen exe 내부에서 성공적으로 통과했고, `--smoke-test`는 FASTA import → project 저장/재오픈 → feature 생성 → GenBank export → semantic reimport 검증까지 실제 packaged 산출물에서 전부 통과했다.
- **재검토 결과 (실제 Windows 머신, 대화형 cmd.exe/PowerShell에서 재검증)**: 실제로 검증해보니 예상과 다른, 더 구체적인 실제 버그를 발견해 고쳤다. `cmd.exe /c "GenomeWorkbench.exe --version > out.txt"`로 파일 리다이렉션했을 때 exit code는 0인데 `out.txt`가 **빈 파일**이었다(반면 `%LOCALAPPDATA%/GenomeWorkbench/last_version_output.json` fallback에는 정상적으로 기록됨 — 즉 명령 자체는 성공했는데 표준출력만 사라짐). 원인: 기존 코드가 `AttachConsole(-1)` 성공 여부만 보고 무조건 `CONOUT$`(콘솔 화면 버퍼)에 다시 연결했는데, 호출자가 이미 표준출력을 파일/파이프로 리다이렉션한 경우에도 이 로직이 실행되어 실제 리다이렉션 대상이 아니라 보이지 않는 백그라운드 콘솔 화면으로 출력을 보내버렸다(Git Bash/mintty는 진짜 Win32 콘솔을 할당하지 않아 `AttachConsole`이 조용히 실패하므로 이 세션 내내 Bash로 실행할 때는 우연히 문제가 드러나지 않았다 — 실제 콘솔을 가진 cmd.exe/PowerShell에서만 재현됨). **수정**: `GetStdHandle`+`GetFileType`으로 STD_OUTPUT_HANDLE/STD_ERROR_HANDLE이 이미 파일(`FILE_TYPE_DISK`) 또는 파이프(`FILE_TYPE_PIPE`)로 연결되어 있는지 먼저 확인하고, 그렇다면 그 핸들로 `sys.stdout`/`sys.stderr`를 재구성한다(`msvcrt.open_osfhandle` + `os.fdopen`) — `AttachConsole`/`CONOUT$` 경로는 리다이렉션이 전혀 없을 때(실제 대화형 콘솔)만 탄다. 수정 후 실제 빌드된 exe로 `cmd.exe /c "... > out.txt"`(파일 리다이렉션)와 PowerShell `| Select-Object`(파이프)를 재검증해 둘 다 `out.txt`/파이프에 실제 텍스트가 정상적으로 잡힘을 확인했다. `--self-test`/`--smoke-test`도 회귀 없이 그대로 통과.

## D-006: 중앙 화면을 text/table에서 실제 genome visualization으로 재설계

- **배경**: 사용자가 Phase 1 결과물을 검토한 뒤, "초보자가 마우스만으로 genome을 탐색·annotation할 수 있는 Geneious 스타일 workbench"를 원했는데 실제로는 sequence 목록 조회기 수준이라고 지적함. "검토 후 진행하지 말고 작업의뢰서(GenomeWorkbench 원본 스펙)대로 끝까지 진행하라"는 명시적 지시를 받음.
- **판단**: Phase 순서를 엄격히 지키는 대신, 사용자가 실제로 가치를 느끼는 부분(Phase 3 시각화, Phase 5/6 BLAST)을 Phase 2(GFF3)보다 먼저 구현했다. `ui/views/genome_canvas.py`(선형, LOD 4단계), `circular_genome_canvas.py`(원형), `minimap.py`, 편집 가능한 `InspectorDock`, 실제 BLAST 파이프라인을 새로 만들고 기존 `QPlainTextEdit` 기반 Sequence/Overview 탭은 완전히 폐기했다.
- **근거**: PROGRESS.md "Phase 3 / BLAST 조기 구현" 절에 상세 체크리스트와 스크린샷 검증 결과를 남김.

## D-007: BLAST database 카탈로그는 project가 아닌 사용자 전역 범위

- **판단**: `BlastService`는 등록된 BLAST database 목록을 project SQLite가 아니라 `%LOCALAPPDATA%/GenomeWorkbench/blast/catalog.json`에 저장한다. 여러 project가 동일한 reference database(예: 표준 AMR gene DB)를 재사용하는 것이 자연스러운 사용 패턴이라고 판단했기 때문이다.
- **테스트 격리**: 이 전역 상태 때문에 자동화 테스트가 실제 사용자 프로필을 오염시키는 문제를 발견했다(동일 이름의 database가 테스트 실행마다 누적됨). `BlastService.__init__(work_dir=...)`와 `MainWindow.__init__(blast_work_dir=...)`에 주입 지점을 추가해 테스트는 `tmp_path`를 사용하고, 프로덕션 기본값은 기존과 동일한 전역 경로를 유지한다.
- **evidence 보존과의 관계**: database가 나중에 삭제/카탈로그에서 제거되어도 이미 적용된 annotation의 근거(Provenance: database_id, checksum, subject_id, identity/evalue/bitscore, raw_result_ref)는 project SQLite에 별도로 영속화되어 있으므로 spec 11.10의 "database가 삭제되어도 evidence summary는 project 안에 남아야 한다" 요구사항은 충족된다.

## D-008: QMenu.exec()는 monkeypatch로 가로챌 수 없음 — 메뉴 표시/처리 분리로 대응

- **문제**: `PySide6.QtWidgets.QMenu`의 `exec()`는 Shiboken이 생성한 바인딩 메서드라서 `monkeypatch.setattr(QMenu, "exec", fake)`로 클래스 속성을 덮어써도 실제 인스턴스 호출에는 반영되지 않는다. `menu.exec(pos)`를 호출하면 진짜 모달 이벤트 루프가 열리고, headless(offscreen) 테스트 환경에는 클릭할 사용자가 없으므로 **영원히 멈춘다**. (반면 `QDialog.exec()`는 동일한 monkeypatch 패턴으로 정상적으로 가로채짐 — `AddFeatureDialog`, `CreateBlastDatabaseDialog`, `ApplyBlastHitDialog` 테스트에서 검증됨.)
- **재현**: 최소 재현 스크립트로 `QMenu.exec = lambda self, *a, **k: self.actions()[0]` 후 `menu.exec(QPoint(0,0))` 호출 시 timeout까지 멈추는 것을 직접 확인함.
- **판단**: `MainWindow._on_canvas_context_menu`(메뉴 생성 + `exec` 호출)와 `MainWindow._dispatch_selection_action(key, start0, end0)`(실제 동작 처리)를 분리했다. 자동화 테스트는 실제 드래그로 만든 selection에 대해 `_dispatch_selection_action("add_annotation", start0, end0)`를 직접 호출해 검증한다 — 모달 없이 동일한 프로덕션 코드 경로를 그대로 실행한다.
- **향후 적용**: 다른 QMenu 기반 UI(예: feature table 우클릭 메뉴)를 추가할 때도 이 패턴(표시/처리 분리)을 재사용할 것.

## D-009: Autosave는 "주기적 스냅샷"이 아니라 "즉시 commit"으로 구현

- **명세**: 12.3절은 "autosave: dirty state일 때 일정 간격 및 주요 mutation 후 debounce"를, 12.4절은 별도의 crash recovery snapshot 목록을 요구한다.
- **현실**: `application/commands.py`의 모든 Command(`FeatureCreateCommand` 등)는 `do()` 시점에 즉시 `repo.save_*()`를 호출하고, `sqlite_repository.py`의 각 save 메서드는 즉시 `self._conn.commit()`한다(Phase 1부터 이미 이런 구조였음). 즉, "편집했지만 아직 저장되지 않은 상태"라는 개념이 애초에 존재하지 않는다 — 매 mutation이 SQLite 파일에 즉시 durable하게 기록된다.
- **판단**: 이 구조를 유지하고, 명세가 요구하는 "데이터 손실 방지"라는 목표를 이미 충족한다고 보아 별도의 주기적 snapshot/debounce 메커니즘을 새로 만들지 않았다. 대신 spec 12.3/12.4의 나머지 목표(동시 열기 감지, 비정상 종료 감지)는 `infrastructure/filesystem/project_lock.py` + `ProjectService.open(force=, read_only=)`로 구현했다: lock file이 close() 시에만 정상적으로 제거되므로, 다음 open 시 lock file이 남아있다는 사실 자체가 "비정상 종료" 신호가 된다.
- **트레이드오프**: "Recover as Copy" 같은 스냅샷 선택 UI는 만들지 않았다 — 잃어버릴 미저장 스냅샷이 없기 때문에 필요성이 낮다고 판단했다. 재검토 조건: 향후 "명시적으로 저장하기 전까지는 변경을 적용하지 않는" 트랜잭션 모델(batch edit, staged changes)이 필요해지면 이 판단을 재검토해야 한다.
- **재검증**: `tests/integration/test_project_service_locking.py`(8 tests)로 lock 획득/해제/충돌/read-only 강제/force-open/stale lock 감지를 검증함.

## D-004: Feature.strand는 단일 값

- 명세 5.2 표는 Feature.strand를 `+1, -1, 0/None` 단일 값으로 정의한다. Biopython의 `CompoundLocation`은 이론상 part마다 다른 strand를 가질 수 있으나(order operator 등 드문 경우), P0 범위에서는 지원하지 않는다.
- **판단**: import 시 part별 strand가 서로 다르면 validation issue(warning)로 보고하고 feature 전체 strand는 다수/첫 part 기준으로 근사한다. 완전한 mixed-strand 지원은 P2 후보로 `KNOWN_LIMITATIONS.md`에 기록한다.
