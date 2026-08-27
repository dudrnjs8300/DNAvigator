# 버전 기록 (Changelog)

DNAvigator의 버전별 변경 사항이다. 최신 버전이 위에 온다.

## v0.5.0 (2026-08-27)

- **Alignment View(신규)**: 이미 정렬(align)된 서열 여러 개를 비교하는 화면 추가.
  **File > Import Alignment...**로 FASTA(gap 포함)/Clustal/Stockholm/PHYLIP/NEXUS/MSF 파일을
  불러오면 Project Explorer에 record와 나란히 표시되고(폴더 정리·이름 변경·삭제 가능), 선택하면
  Alignment View 탭이 열린다. 위쪽에 consensus 서열과 위치별 변이 정도를 보여주는 conservation
  bar가 고정 표시되고, 각 서열은 염기/아미노산별로 색이 칠해지며 consensus와 일치하는 칸은 옅게,
  다른 칸은 진하게 표시되어 서열 간 차이가 확대하지 않아도 한눈에 보인다. **View > Alignment
  Colors...**로 색을 커스터마이즈할 수 있고, Genome Map/Circular Map과 마찬가지로 이미지로
  내보낼 수 있다. Genome Map과 동일하게 화면에 보이는 부분만 그리는 방식이라 서열 수·길이가
  많아져도 무겁지 않다.

## v0.4.0 (2026-08-27)

- **유전자 이름 표시 개선**: Genome Map에서 전체 genome을 보는 최대 축소 상태만 아니면 유전자
  이름(label)이 바로 보이도록 변경. 이전에는 아주 가깝게 확대해야만 이름이 보였다.
- **Circular Map 커서 기준 확대**: 마우스 휠로 확대할 때 링의 고정된 중심이 아니라 커서가 있는
  위치를 기준으로 확대되도록 수정. 보고 있던 유전자가 확대 중 화면 밖으로 밀려나는 문제 해결.
- **구간 복사 → 붙여넣기(신규)**: Genome Map/Circular Map에서 원하는 부위를 Ctrl+C로 복사하고,
  Project Explorer에서 record나 폴더를 선택한 뒤 Ctrl+V를 누르면 그 구간만 잘라낸 새 record가
  annotation과 함께 생성된다. 구간 안에 완전히 포함된 feature만 좌표가 재계산되어 함께 복사되고,
  기존 "Extract Selection as New Record" 메뉴도 이제 annotation을 함께 옮긴다(이전에는 서열만
  복사되고 annotation은 유실됐다).

## v0.3.0 (2026-08-27)

- **키보드 단축키**: Project Explorer에서 Delete 키로 record/폴더 삭제, Genome Map/Circular
  Map/Feature Table에서 Ctrl+C로 서열·feature 정보 복사.
- **Feature 색상 커스터마이즈**: View > Feature Colors...에서 feature 타입별 색상을 직접
  지정하고 저장(사용자 단위로 프로젝트와 무관하게 유지됨).
- **논문용 고화질 이미지 내보내기**: View > Export View as Image...로 Genome Map/Circular Map을
  PNG(최대 4배 해상도)/SVG로 저장.
- **렌더링 품질 개선**: antialiasing 적용, feature 화살표에 입체감 있는 그라데이션 추가.

## v0.2.0 (2026-08-27)

- **제품명 변경**: "GenomeWorkbench"에서 "DNAvigator"로 브랜드 변경(Google 검색 시 이름이 너무
  흔해서 찾기 어렵다는 문제 해결). 내부 Python 패키지 경로(`genome_workbench`)와 프로젝트 파일
  확장자(`.gwbproj`)는 사용자에게 보이지 않는 내부 구현이라 그대로 유지.

## v0.1.1 (2026-08-27)

- **SQLite 성능 개선**: 대량 import/feature 저장 시 매 건마다 fsync하지 않고 트랜잭션을 묶어
  처리(6,000 feature 기준 GenBank import가 약 86초 → 5초 이내로 단축). 프로젝트 재오픈 시
  feature 목록을 N+1 쿼리 대신 JOIN 기반으로 한 번에 로드(약 6.5초 → 500ms 이내).
- **다크 테마 대비 수정**: Genome Map/Circular Map의 색상을 팔레트 기반으로 바꿔 다크 테마에서도
  텍스트/선이 잘 보이도록 개선.
- **CLI 출력 버그 수정**: 실행 파일을 터미널에서 리다이렉트로 실행할 때 표준 출력이 조용히
  사라지던 버그 수정(`AttachConsole` 관련 `GetFileType` 검사 추가).
- **`.gwbproj` 파일 연결 크래시 수정**: 탐색기에서 프로젝트 파일을 더블클릭해 실행 파일에 인자로
  넘겼을 때 발생하던 크래시 수정.
- **Record 삭제 / 폴더 트리**: Project Explorer에서 record를 삭제하고, 중첩 폴더를 만들어
  record를 정리할 수 있게 됨.
- **Circular Map 마우스 조작**: 휠로 확대/축소, 드래그로 회전.
- **BLAST job 취소**, **blastp/blastx/tblastn 실제 바이너리 검증**, **Tool Setup Wizard 자동
  다운로드**.
- GitHub Actions에서 태그 푸시 시 설치 프로그램이 첨부된 Release를 자동 발행하도록 설정, README를
  비개발자 대상으로 재작성(설치 프로그램을 먼저 안내).

## v0.1.0 (2026-08-27) — 첫 배포

DNA/단백질 서열을 시각화하고 annotation을 붙여 관리하는 Windows 프로그램의 첫 배포판.

- FASTA / GenBank / GFF3 import, GenBank / GFF3 / FASTA(nucleotide, protein) / FFN / feature CSV
  export.
- Genome Map(선형)과 Circular Map을 갖춘 실제 genome visualization 엔진(확대 수준에 따라
  밀도 그래프 → strand 화살표 → 염기 문자로 자동 전환).
- 수동 annotation 생성/편집: qualifier 전체 편집기, join/compound location UI, fuzzy(</>) 경계
  표시, 자동 저장(프로젝트 파일에 즉시 커밋).
- BLAST+ 연동: 로컬 DB 생성, 단일/배치(여러 feature 동시) 검색, 검색 결과를 근거로 한 annotation
  자동 채우기, 작업 취소.
- record 추출(선택 구간을 새 record로), reverse complement, 비파괴적 서열 조작.
- Batch qualifier 연산과 annotation 템플릿.
- Project Explorer에 폴더 트리, record 삭제.
- gene/qualifier 이름으로 찾기(Ctrl+F).
- Windows 설치 프로그램(Inno Setup) 및 GitHub Actions 기반 자동 빌드/릴리스.

---

각 버전에 대응하는 정확한 코드 변경 내역은 `git log`와 GitHub Releases
(https://github.com/dudrnjs8300/DNAvigator/releases)에서 확인할 수 있다.
