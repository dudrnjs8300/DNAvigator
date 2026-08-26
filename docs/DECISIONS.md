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
- **재검토 조건**: Phase 8에서 실제 대화형 터미널 및 GitHub Actions windows-latest runner에서 `AttachConsole` 경로 자체도 재검증한다.

## D-004: Feature.strand는 단일 값

- 명세 5.2 표는 Feature.strand를 `+1, -1, 0/None` 단일 값으로 정의한다. Biopython의 `CompoundLocation`은 이론상 part마다 다른 strand를 가질 수 있으나(order operator 등 드문 경우), P0 범위에서는 지원하지 않는다.
- **판단**: import 시 part별 strand가 서로 다르면 validation issue(warning)로 보고하고 feature 전체 strand는 다수/첫 part 기준으로 근사한다. 완전한 mixed-strand 지원은 P2 후보로 `KNOWN_LIMITATIONS.md`에 기록한다.
