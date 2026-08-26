# 알려진 제한 (KNOWN_LIMITATIONS.md)

현재(Phase 1 + Phase 3/BLAST 조기 구현 시점) 구현 상태 기준. 각 항목은 해결 예정 phase를 함께 표기한다.

## 시각화

- **Circular map의 zoom/rotation 없음** (Phase 3 나머지 범위). Click/hover/double-click selection은 동작하지만 원형 지도 자체를 확대하거나 회전할 수는 없다.
- **10,000+ feature 규모의 렌더링 성능 벤치마크 미실시** (Phase 3 gate, 5.5 Mb/6,000 feature). `FeatureIntervalIndex`는 spec 8.3 권장 방식(sorted start + bisect, 최대 feature 길이로 범위 제한)으로 구현되어 있으나 대규모 실측은 아직 없다.
- **DPI(125/150/200%) 및 다크/라이트 테마 미검증** (Phase 7). offscreen 플랫폼에서만 자동 검증했다.

## Annotation

- **Fuzzy location을 마우스로 만드는 UI가 없음** (Phase 4 나머지 범위). Compound(join) location은 `AddFeatureDialog`의 "Multiple segments (join)" 체크박스로 생성 가능해졌다(세그먼트를 임의 순서로 입력해도 strand에 따른 생물학적 순서(D-002)로 자동 정렬됨). Fuzzy(`<`/`>`) boundary 입력은 여전히 없음 — domain/adapter는 완전히 지원하고 import 시 보존한다.
- **기존 compound feature의 part 목록을 Inspector에서 재편집할 수 없음.** Inspector는 여전히 단일 구간(simple) 좌표 편집만 지원한다. Feature 경계 drag-resize도 단일 part feature에만 동작하며, compound feature는 크기 조정 시 명확한 오류 메시지를 표시하고 거부한다(자동 처리 대신 안전하게 실패).
- **Batch qualifier 연산, annotation template 없음** (Phase 4 나머지 범위). Qualifier 편집은 공통 6개 필드(quick access) + "All other qualifiers" 자유 key/value 테이블(추가/삭제/multi-value)로 개별 feature 단위에서는 완전하지만, 여러 feature를 한 번에 편집하는 기능은 없다.
- **Batch BLAST(여러 feature 동시 검색) 미지원** — 한 번에 하나의 selection/query만 처리한다 (Phase 6 나머지 범위).

## 파일 형식

- **GTF/EMBL/BED 미지원** — 지원한다고 표시하지 않음(의도된 범위 밖, P0 대상 아님). GFF3와 GenBank record-level metadata는 Phase 2에서 완료됨(`docs/FORMAT_SUPPORT.md` 참고).

## BLAST

- **실제 NCBI BLAST+ 바이너리로 검증되지 않음.** 이 개발 환경에 BLAST+가 설치되어 있지 않아, 파이프라인 전체(command 구성 → subprocess 실행 → stdout 파싱 → 좌표 매핑 → annotation 적용)는 `tests/fixtures/fake_blast/*.bat`라는 대역 실행파일로 검증했다. Detector/command_builder는 실제 `makeblastdb.exe`/`blastn.exe` 등의 이름과 `-version`/`-outfmt 6 ...` 인터페이스를 그대로 사용하도록 작성했으므로 실제 BLAST+ 설치 시 동작할 것으로 예상하지만, **실제 바이너리로 재검증 전까지는 확정된 것이 아니다**. Phase 6에서 실제 BLAST+ 설치 환경으로 재검증 필요.
- **BLAST database 카탈로그가 project가 아닌 사용자 전역(`%LOCALAPPDATA%/GenomeWorkbench/blast/catalog.json`)에 저장됨.** 여러 project에서 동일 DB를 재사용할 수 있다는 장점이 있지만, project 삭제 시 DB가 함께 정리되지 않는다. Provenance(적용된 annotation의 근거)는 project SQLite에 별도로 영속화되므로 DB가 나중에 삭제되어도 evidence summary 자체는 남는다(spec 11.10 요구사항 충족).
- **`--self-test`의 `blast_executable` 항목은 여전히 `optional_tool_unavailable`로 분류됨** — BLAST+ 미설치가 core self-test 실패를 유발하지 않는다.
- **Tool Setup Wizard의 공식 배포판 자동 다운로드 경로 없음** (Phase 5). 현재 `BlastSetupDialog`는 기존 설치 탐지와 수동 디렉터리 지정만 지원한다.
- **번역 검색(blastx/tblastn)의 frame 기반 좌표 매핑이 근사적임.** `map_hsp_to_genome_location`은 blastn(뉴클레오타이드 대 뉴클레오타이드) 기준으로 검증되었고, 단위 테스트 4건(정방향/역방향 query × subject strand 조합)을 통과했다. blastx/tblastn의 세부 frame 처리는 Phase 6에서 추가 검증 필요.

- **별도의 주기적 autosave/snapshot이 없다 — 대신 모든 mutation이 즉시 SQLite에 commit된다.** `application/commands.py`의 각 Command는 실행 즉시 `repo.save_*()`를 호출해 커밋하므로, "저장 안 된 편집 내용"이라는 개념 자체가 없다(잃어버릴 미저장 상태가 없음). `Save`(Ctrl+S)는 `modified_at` timestamp만 갱신하는 사실상 의례적인 동작이다. 이는 spec 12.3이 요구하는 것과 메커니즘은 다르지만(주기적 snapshot이 아니라 즉시 commit) 데이터 손실 방지라는 목표는 동등하게(사실 더 강하게) 충족한다.
- **Project lock(동시 열기 감지)과 비정상 종료 감지는 구현됨.** `infrastructure/filesystem/project_lock.py` + `ProjectService`: 두 번째 instance가 같은 project를 열려고 하면 읽기 전용으로 열거나 강제로 편집 모드로 열 수 있는 선택지를 제공한다(spec 12.3). 이전 세션이 비정상 종료되어 lock file이 남아있으면 다음 open 시 동일한 경고가 뜬다(spec 12.4의 "비정상 종료 marker" 요구사항에 상응). 다만 "Recover as Copy" UI(스냅샷 목록에서 선택)는 없다 — 애초에 잃어버릴 미저장 스냅샷이 없으므로 필요성이 낮다고 판단했다.
- **Undo stack이 session 간 유지되지 않음** (설계상 의도됨 — project를 닫으면 초기화).
- **Record topology 변경(linear/circular)이 undo 불가능** — `ProjectService.set_record_topology`는 undo stack을 거치지 않는 단순 mutation이다. 실수로 변경해도 되돌리기는 다시 우클릭으로 반대 값을 선택해야 한다.

## 패키징 / 배포

- **Installer(Inno Setup), file association, code signing 없음** (Phase 8). 현재는 PyInstaller onedir 산출물만 있으며 portable 형태로만 확인했다.
- **`AttachConsole` 기반 CLI 출력 경로가 실제 대화형 터미널/CI에서 미검증** — `docs/DECISIONS.md` D-005 참고. 대신 모든 CLI 명령 결과를 `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json`에 항상 기록하도록 했다.
- **한국어 사용자 매뉴얼(`USER_GUIDE_KO.md`), `BLAST_SETUP.md`, 완전한 `FORMAT_SUPPORT.md` compatibility matrix 아직 없음** (Phase 8, 일부는 Phase 2에서 시작).

## 테스트

- **GitHub Actions에서 실제로 실행되지 않음.** `.github/workflows/*.yml`은 작성되었고 로컬에서 동일 명령으로 수동 검증했지만, 원격 저장소 push 및 실제 Actions 실행 확인은 사용자 승인이 필요하다.
- **`QMenu.exec()`는 자동화 테스트에서 monkeypatch로 가로챌 수 없음** (PySide6/Shiboken 바인딩 메서드 특성). `ui/main_window.py`의 컨텍스트 메뉴 로직은 "메뉴 표시"(`_on_canvas_context_menu`)와 "동작 처리"(`_dispatch_selection_action`)로 분리되어 있고, 테스트는 후자를 직접 호출한다. 새로운 QMenu 기반 UI를 추가할 때 이 패턴을 재사용할 것.
