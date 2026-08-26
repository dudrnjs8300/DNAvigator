# 알려진 제한 (KNOWN_LIMITATIONS.md)

현재(Phase 1 완료 시점) 구현 상태 기준. 각 항목은 해결 예정 phase를 함께 표기한다.

## 시각화

- **Sequence view가 완전한 virtualized custom painter가 아님** (Phase 3에서 구현 예정). 현재는 `QPlainTextEdit` 기반으로 전체 서열을 60-컬럼 wrap하여 표시한다. Qt가 내부적으로 line 단위 lazy layout을 하므로 bacterial-scale(수 Mb) genome에서도 열람 자체는 가능하지만, feature highlight track, base-level click-to-select genomic coordinate mapping, LOD(Level of Detail) 전환은 아직 없다.
- **Linear/circular genome map이 없음** (Phase 3). 현재 UI는 Overview/Sequence/Feature Table 탭만 제공한다.
- **Minimap, drag boundary editing, GC content/skew track 없음** (Phase 3).

## Annotation

- **Compound(join)/fuzzy location을 만드는 UI가 없음** (Phase 2/4). `AnnotationService.create_simple_feature`는 단일 LocationPart만 생성한다. Domain 계층(`domain/locations.py`)은 compound/fuzzy를 완전히 지원하며 GenBank adapter도 import 시 이를 보존하지만, 수동 생성 dialog에서는 아직 노출하지 않는다.
- **qualifier 편집기가 read-only 미리보기뿐** (Phase 4). Inspector dock은 현재 조회 전용이며, 생성 dialog에서만 gene/product/note/transl_table 4개 qualifier를 입력할 수 있다. "all qualifiers" key/value 편집기, batch qualifier 연산, template은 없음.
- **batch BLAST, annotation template, drag handle 좌표 조정 없음** (Phase 4/6).

## 파일 형식

- **GFF3 adapter가 없음** (Phase 2). import/export 모두 FASTA와 GenBank만 지원한다.
- **GenBank record-level metadata(organism, taxonomy, references, comments)가 최소한만 보존됨.** 현재 `SequenceRecord.annotations_json`은 기본값 `"{}"`로 남아있고 GenBank adapter가 이를 채우지 않는다 — export 시 해당 필드들이 유실된다는 뜻은 아니지만(원본 GenBank의 이 정보를 아직 domain model에 매핑하지 않았을 뿐), round-trip 시 record-level 부가정보는 보존되지 않는다. Phase 2에서 해결.
- **GTF/EMBL/BED 미지원** — 지원한다고 표시하지 않음(의도된 범위 밖, P0 대상 아님).

## BLAST

- **전혀 구현되지 않음** (Phase 5/6). 메뉴에 "BLAST Setup...", "Run BLAST..." 항목이 보이지만 명시적으로 비활성화되어 있고 tooltip으로 안내한다. `--self-test`의 `blast_executable` 항목은 `optional_tool_unavailable`로 분류되어 core self-test 실패를 유발하지 않는다.

## Project / 저장

- **Autosave, crash recovery, project lock(동시 열기 감지) 없음** (Phase 4). 현재는 명시적 `Save`(즉시 commit)만 있다.
- **Undo stack이 session 간 유지되지 않음** (설계상 의도됨 — project를 닫으면 초기화). Autosave와의 상호작용은 Phase 4에서 설계.

## 성능

- **5.5 Mb/6,000 feature 벤치마크 미실시** (Phase 3 gate). 현재 vertical slice는 1 kb 규모 fixture로만 검증되었다.

## 패키징 / 배포

- **Installer(Inno Setup), file association, code signing 없음** (Phase 8). 현재는 PyInstaller onedir 산출물만 있으며 portable 형태로만 확인했다.
- **`AttachConsole` 기반 CLI 출력 경로가 실제 대화형 터미널/CI에서 미검증** — `docs/DECISIONS.md` D-005 참고. 대신 모든 CLI 명령 결과를 `%LOCALAPPDATA%/GenomeWorkbench/last_*_output.json`에 항상 기록하도록 했다.
- **BLAST+ 재배포 관련 Tool Setup Wizard 없음** (Phase 5). 라이선스 검토 전이므로 자동 다운로드/설치 경로도 아직 없다.
- **한국어 사용자 매뉴얼(`USER_GUIDE_KO.md`), `BLAST_SETUP.md`, 완전한 `FORMAT_SUPPORT.md` compatibility matrix 아직 없음** (Phase 8, 일부는 Phase 2에서 시작).

## 테스트

- **GitHub Actions에서 실제로 실행되지 않음.** `.github/workflows/*.yml`은 작성되었고 로컬에서 동일 명령으로 수동 검증했지만, 원격 저장소 push 및 실제 Actions 실행 확인은 사용자 승인이 필요하다.
- **UI 자동화 테스트가 pytest-qt 기반 offscreen platform으로만 검증됨.** 실제 Windows 데스크톱 세션에서의 DPI(125/150/200%), 다크/라이트 테마는 아직 확인하지 않았다(Phase 3/7).
