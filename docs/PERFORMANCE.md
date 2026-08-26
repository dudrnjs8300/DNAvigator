# 성능·호환성 측정 보고서 (PERFORMANCE.md)

spec 21절 형식에 따라 release마다 기록한다. 수치를 과장하지 않고 측정 조건과 변동성을 함께 남긴다.

## 측정일: 2026-08-27

## 측정 환경

- OS: Windows 10 Home 10.0.19045 (build 19045)
- CPU: AMD Ryzen 5 3600 6-Core Processor
- RAM: 32 GB
- Storage: 측정하지 않음(디스크 종류 미확인 — 이 항목은 정직하게 미기록으로 남긴다)
- App version: 0.1.0
- Python: 3.14.6
- PySide6/Qt: 6.11.2 / 6.11.2
- Biopython: 1.88
- BLAST+: NCBI BLAST 2.17.0+ (win64, 공식 배포판, 별도 세션에서 검증)
- 측정 방식: `QT_QPA_PLATFORM=offscreen`, `scratch/run_performance_benchmark.py`(gitignore됨, 재실행 가능한 벤치마크 스크립트)

## Fixture

- 합성(synthetic) 5.5 Mb / 6,000 CDS feature bacterial-scale genome, GenBank 형식으로 생성
- Feature: 길이 200~1500bp 무작위, strand 무작위(+/-), 균등 분포, qualifier 3종(gene/locus_tag/product)
- 생성된 GenBank 파일 크기: 7.8 MB

## 결과 요약

| 항목 | 측정값 | spec 8.4 목표 | 비고 |
|---|---|---|---|
| GenBank import (5.5Mb, 6,000 feature) | **0.86s** | ≤ 5s | ✅ 목표의 1/6 |
| Project reopen + list_features (warm) | **194ms** | ≤ 500ms | ✅ |
| Project touch(save) | 12.4ms | (명시적 목표 없음) | |
| FeatureIntervalIndex 생성(6,000 feature) | 16.4ms | (명시적 목표 없음) | |
| Viewport query (200 샘플) | median 0.03ms, p95 0.31ms | (명시적 목표 없음) | |
| 전체 genome overview 렌더 | median 20.0ms | 30fps(33ms) 또는 ≤100ms latency | ✅ |
| gene-level(~50kb) 렌더 | median 2.1ms | 〃 | ✅ |
| feature-level(~5kb) 렌더 | median 0.9ms | 〃 | ✅ |
| base-level(~200bp) 렌더 | median 6.3ms | 〃 | ✅ |
| Pan 연속 조작(30 frame, feature-level) | median 0.9ms(~1092fps 상당) | ≥30fps 또는 ≤100ms | ✅ |
| Export GenBank + semantic reimport validation | 2.13s (diff 0건) | (명시적 목표 없음) | |

**결론: 5개 spec 8.4 목표 전부 충족.** Phase 3 gate("5.5 Mb/6,000 feature synthetic benchmark", "interactive pan/zoom")를 실측으로 통과했다.

## 이번 측정에서 발견하고 고친 실제 성능 버그

최초 측정에서 import가 **86.13s**(목표 5s의 17배), project reopen이 **6478.7ms**(목표 500ms의 13배)로 크게 벗어났다. 렌더링/pan/zoom은 처음부터 목표를 크게 상회했으므로(수 ms 단위), 문제는 시각화 엔진이 아니라 SQLite 저장소 계층에 있었다.

1. **`ProjectRepository.save_feature`/`save_record`가 호출마다 `commit()`을 실행**했다. SQLite의 기본 `commit()`은 디스크 fsync를 수반하므로, feature 6,000개를 개별 저장하면 fsync 6,000회가 그대로 소요 시간이 된다. `application/import_service.py`의 import 루프가 `repo.save_feature(feature)`를 feature마다 호출하고 있었다.
   - **수정**: `save_feature`/`save_record`에 `commit: bool = True` 매개변수를 추가하고, 여러 건을 한 번의 commit으로 저장하는 `save_features_bulk`/`save_records_bulk`를 추가했다. Import 3종(FASTA/GenBank/GFF3) 모두 이 bulk 메서드를 사용하도록 변경했다. 단일 feature를 편집하는 기존 UI 경로(Inspector Apply 등)는 그대로 `save_feature`(commit=True 기본값)를 써서, D-009가 요구하는 "즉시 commit = 잃어버릴 미저장 상태 없음" 원칙은 그대로 유지된다 — 오직 "여러 건을 한 번에 쓰는" 경로만 최적화했다.
2. **`list_features`가 feature마다 4개의 추가 쿼리**(location_part/qualifier/child 관계/parent 관계)를 실행하는 N+1 패턴이었다. 6,000 feature 기준 약 24,000개의 개별 SQL 쿼리가 발생했다.
   - **수정**: `list_features`를 `feature` 테이블과 관련 테이블 4개를 각각 record 단위로 JOIN하는 고정 쿼리 4~5개로 재작성했다. Python 쪽에서 feature_id별로 그룹핑한 뒤 조립한다. `get_feature`(단일 feature 조회)는 그대로 두었다 — 한 건 조회에는 N+1이 의미 없다.

수정 후: import 86.13s → **0.86s**(100배), reopen 6478.7ms → **194.3ms**(33배). 두 회귀 모두 `tests/integration/test_sqlite_repository.py`에 테스트로 고정했다(commit 호출 횟수를 세는 테스트, bulk-JOIN 결과가 건별 조회와 정확히 일치하는지 검증하는 테스트 — wall-clock 시간이 아니라 동작 자체를 검증해 flaky하지 않게 했다).

## High-DPI / 테마 확인

Qt6는 기본적으로 `Qt::AA_EnableHighDpiScaling`이 켜져 있어 별도 설정 없이 125/150/200% 배율에서 자동 스케일링된다. `QT_SCALE_FACTOR=1.0/1.25/1.5/2.0` 각각에서 `MainWindow`를 offscreen 플랫폼으로 실행해 크래시 없음과 `devicePixelRatioF()`가 기대값과 일치함을 확인했다.

다크 팔레트 검증 중 **실제 가독성 버그를 발견해 고쳤다**: `GenomeCanvas`/`CircularGenomeCanvas`는 배경을 `palette().base()`로 채워 테마를 따라가지만, 눈금자·염기 서열 텍스트·선택 표시 등 전경색 다수가 `#111111`/`#333333`/`#555555`/`#777777` 같은 고정 진회색 hex 값이었다. 밝은 팔레트에서는 문제없지만 어두운 팔레트(배경이 `#232323` 근처)에서는 거의 안 보이는 수준의 대비였다(WCAG 대비율 실측 1.5 미만, AA 기준 4.5 미달). `palette().color(QPalette.ColorRole.Text)`(주 전경) / `PlaceholderText`(보조 전경, 상보 가닥 텍스트 등) / `Highlight`(선택 표시)로 교체해 라이트/다크 어느 팔레트에서도 배경과의 대비가 확보되도록 고쳤다. 수정 후 실측 대비율: 다크 팔레트에서 본문 텍스트 11.46:1, 보조 텍스트 5.31:1, 라이트 팔레트에서 21:1(AA 기준 4.5:1을 모두 크게 상회). `tests/ui/test_canvas_theme_contrast.py`(4건)로 회귀 방지. Feature 타입별 색상(`feature_colors.py`)과 선택/강조용 강조색(파랑·빨강 계열)은 테마와 무관하게 판독 가능한 채도를 갖도록 의도적으로 고정되어 있어 그대로 두었다.

실제 Windows 디스플레이 설정 변경을 통한 육안 확인(사람이 스크린을 보고 최종 판단하는 것)은 이 자동화 환경에서 할 수 없다는 한계는 남아 있다 — 위 수치는 계산된 대비율 기반 검증이다.

## 재현 방법

```bash
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe scratch/run_performance_benchmark.py
```

`scratch/`는 gitignore 대상이라 스크립트 자체는 저장소에 없다 — 필요 시 이 문서의 스크립트 로직을 참고해 재작성한다. (이 결정은 재고할 수 있다: 재현성을 위해 스크립트를 `scripts/`로 옮겨 추적하는 것도 합리적이다.)
