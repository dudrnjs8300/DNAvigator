# 알려진 제한 (KNOWN_LIMITATIONS.md)

현재(Phase 1 + Phase 3/BLAST 조기 구현 시점) 구현 상태 기준. 각 항목은 해결 예정 phase를 함께 표기한다.

## 시각화

- **Circular map의 zoom/rotation 없음** (Phase 3 나머지 범위). Click/hover/double-click selection은 동작하지만 원형 지도 자체를 확대하거나 회전할 수는 없다.
- **10,000+ feature 규모의 렌더링 성능 벤치마크 미실시** (Phase 3 gate, 5.5 Mb/6,000 feature). `FeatureIntervalIndex`는 spec 8.3 권장 방식(sorted start + bisect, 최대 feature 길이로 범위 제한)으로 구현되어 있으나 대규모 실측은 아직 없다.
- **DPI(125/150/200%) 및 다크/라이트 테마 미검증** (Phase 7). offscreen 플랫폼에서만 자동 검증했다.

## Annotation

- **Compound(join)/fuzzy location을 마우스로 만드는 UI가 없음** (Phase 4). `AnnotationService.create_simple_feature`와 canvas의 drag-select/context-menu 흐름은 단일 LocationPart만 생성한다. Domain 계층(`domain/locations.py`)과 GenBank adapter는 compound/fuzzy를 완전히 지원하며 import 시 보존하지만, 수동 생성 경로에서는 아직 노출하지 않는다.
- **Feature 경계 drag-resize가 단일 part feature에만 동작함** (`ui/views/genome_canvas.py`). Compound feature는 크기 조정 시 명확한 오류 메시지를 표시하고 거부한다(자동 처리 대신 안전하게 실패).
- **Qualifier 편집기가 공통 6개 필드만 지원** (gene/locus_tag/product/note/db_xref/inference). "전체 qualifiers" key/value 자유 편집기, batch qualifier 연산, annotation template은 아직 없음 (Phase 4).
- **Batch BLAST(여러 feature 동시 검색) 미지원** — 한 번에 하나의 selection/query만 처리한다 (Phase 6 나머지 범위).

## 파일 형식

- **GFF3 adapter가 없음** (Phase 2). import/export 모두 FASTA와 GenBank만 지원한다.
- **GenBank record-level metadata(organism, taxonomy, references, comments)가 최소한만 보존됨.** `SequenceRecord.annotations_json`은 기본값 `"{}"`로 남아있고 GenBank adapter가 이를 채우지 않는다. Phase 2에서 해결 예정.
- **GTF/EMBL/BED 미지원** — 지원한다고 표시하지 않음(의도된 범위 밖, P0 대상 아님).

## BLAST

- **실제 NCBI BLAST+ 바이너리로 검증되지 않음.** 이 개발 환경에 BLAST+가 설치되어 있지 않아, 파이프라인 전체(command 구성 → subprocess 실행 → stdout 파싱 → 좌표 매핑 → annotation 적용)는 `tests/fixtures/fake_blast/*.bat`라는 대역 실행파일로 검증했다. Detector/command_builder는 실제 `makeblastdb.exe`/`blastn.exe` 등의 이름과 `-version`/`-outfmt 6 ...` 인터페이스를 그대로 사용하도록 작성했으므로 실제 BLAST+ 설치 시 동작할 것으로 예상하지만, **실제 바이너리로 재검증 전까지는 확정된 것이 아니다**. Phase 6에서 실제 BLAST+ 설치 환경으로 재검증 필요.
- **BLAST database 카탈로그가 project가 아닌 사용자 전역(`%LOCALAPPDATA%/GenomeWorkbench/blast/catalog.json`)에 저장됨.** 여러 project에서 동일 DB를 재사용할 수 있다는 장점이 있지만, project 삭제 시 DB가 함께 정리되지 않는다. Provenance(적용된 annotation의 근거)는 project SQLite에 별도로 영속화되므로 DB가 나중에 삭제되어도 evidence summary 자체는 남는다(spec 11.10 요구사항 충족).
- **`--self-test`의 `blast_executable` 항목은 여전히 `optional_tool_unavailable`로 분류됨** — BLAST+ 미설치가 core self-test 실패를 유발하지 않는다.
- **Tool Setup Wizard의 공식 배포판 자동 다운로드 경로 없음** (Phase 5). 현재 `BlastSetupDialog`는 기존 설치 탐지와 수동 디렉터리 지정만 지원한다.
- **번역 검색(blastx/tblastn)의 frame 기반 좌표 매핑이 근사적임.** `map_hsp_to_genome_location`은 blastn(뉴클레오타이드 대 뉴클레오타이드) 기준으로 검증되었고, 단위 테스트 4건(정방향/역방향 query × subject strand 조합)을 통과했다. blastx/tblastn의 세부 frame 처리는 Phase 6에서 추가 검증 필요.

## Project / 저장

- **Autosave, crash recovery, project lock(동시 열기 감지) 없음** (Phase 4). 현재는 명시적 `Save`(즉시 commit)만 있다.
- **Undo stack이 session 간 유지되지 않음** (설계상 의도됨 — project를 닫으면 초기화).
- **Record topology 변경(linear/circular)이 undo 불가능** — `ProjectService.set_record_topology`는 undo stack을 거치지 않는 단순 mutation이다. 실수로 변경해도 되돌리기는 다시 우클릭으로 반대 값을 선택해야 한다.

## 패키징 / 배포

- **Installer(Inno Setup), file association, code signing 없음** (Phase 8). 현재는 PyInstaller onedir 산출물만 있으며 portable 형태로만 확인했다.
- **`AttachConsole` 기반 CLI 출력 경로가 실제 대화형 터미널/CI에서 미검증** — `docs/DECISIONS.md` D-005 참고. 대신 모든 CLI 명령 결과를 `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json`에 항상 기록하도록 했다.
- **한국어 사용자 매뉴얼(`USER_GUIDE_KO.md`), `BLAST_SETUP.md`, 완전한 `FORMAT_SUPPORT.md` compatibility matrix 아직 없음** (Phase 8, 일부는 Phase 2에서 시작).

## 테스트

- **GitHub Actions에서 실제로 실행되지 않음.** `.github/workflows/*.yml`은 작성되었고 로컬에서 동일 명령으로 수동 검증했지만, 원격 저장소 push 및 실제 Actions 실행 확인은 사용자 승인이 필요하다.
- **`QMenu.exec()`는 자동화 테스트에서 monkeypatch로 가로챌 수 없음** (PySide6/Shiboken 바인딩 메서드 특성). `ui/main_window.py`의 컨텍스트 메뉴 로직은 "메뉴 표시"(`_on_canvas_context_menu`)와 "동작 처리"(`_dispatch_selection_action`)로 분리되어 있고, 테스트는 후자를 직접 호출한다. 새로운 QMenu 기반 UI를 추가할 때 이 패턴을 재사용할 것.
