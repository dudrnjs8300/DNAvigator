# BLAST+ 설치 및 설정 (BLAST_SETUP.md)

GenomeWorkbench는 NCBI BLAST+ 실행파일을 포함하지 않는다(재배포 조건 미검토, `docs/LICENSING.md` 참고). 사용자가 직접 설치하거나 이미 설치된 것을 등록해야 한다.

> **이 문서의 검증 상태**: 1절의 절차(공식 NCBI FTP에서 `ncbi-blast-2.17.0+-win64.exe` 다운로드 → MD5 확인 → silent 설치 `/S`)를 이 개발 머신에서 실제로 수행했고, GenomeWorkbench의 BLAST 파이프라인(설치 자동 탐지, 실제 `makeblastdb`로 nucleotide/protein database 생성, 실제 `blastn`/`blastp`/`blastx`/`tblastn` 실행, 결과 파싱, 좌표 매핑, annotation 적용)을 4개 프로그램 전부 실제 바이너리로 검증했다(`tests/integration/test_blast_real_installation.py`). 2절의 앱 내장 자동 다운로드 경로도 이제 구현되어 있다.

## 1. 공식 BLAST+ 설치

1. https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ 에서 Windows용 최신 안정 버전(예: `ncbi-blast-X.Y.Z+-x64-win64.exe` 또는 `.zip`)을 내려받는다.
2. 설치하거나 압축을 해제한다. `bin` 폴더 안에 다음 실행파일이 있는지 확인한다.
   - `makeblastdb.exe`
   - `blastdbcmd.exe`
   - `blastn.exe`
   - `blastp.exe`
   - `blastx.exe`
   - `tblastn.exe`
3. GenomeWorkbench에서 **BLAST > BLAST Setup...** 을 연다.
4. 설치 경로(`bin` 폴더)를 "BLAST+ bin directory"에 입력하거나 **Browse...** 로 선택한 뒤 **Detect**를 누른다.
5. 6개 실행파일이 모두 "[OK]"로 표시되고 각 버전 정보가 보이면 설정이 끝난 것이다.

이미 BLAST+가 시스템 PATH에 등록되어 있다면 경로를 비워두고 **Detect**만 눌러도 자동으로 찾는다.

## 2. app-managed 자동 설치

**BLAST > BLAST Setup...** 대화상자의 **Download & Install BLAST+ (official NCBI build)** 버튼을 누르면 다음을 자동으로 수행한다:

1. NCBI의 release index 페이지(`ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/`)에서 최신 Windows 이식용 배포판(`ncbi-blast-X.Y.Z+-x64-win64.tar.gz`) 파일명을 동적으로 찾는다 — 특정 버전을 하드코딩하지 않으므로 NCBI가 새 버전을 내면 자동으로 그것을 받는다.
2. 다운로드 전 대상 크기(~140MB)와 설치 경로를 안내하는 확인 대화상자를 띄운다.
3. 다운로드하면서 NCBI가 함께 게시하는 MD5 체크섬 파일(`.tar.gz.md5`)과 비교해 무결성을 검증한다 — 일치하지 않으면 설치를 중단하고 부분 다운로드 파일을 지운다.
4. `%LOCALAPPDATA%\GenomeWorkbench\tools\blast+\<버전>\`에 압축을 푼다(설치 프로그램이 아니라 단순 압축 해제이므로 관리자 권한이 필요 없다).
5. 압축이 풀린 `bin` 폴더로 자동 재탐지한다.

다운로드는 UI를 막지 않도록 별도 스레드에서 진행되며, 진행률 표시줄과 **Cancel** 버튼으로 중단할 수 있다.

**offline archive를 직접 선택해 설치하는 경로는 아직 없다** — 오프라인 환경에서는 여전히 1절처럼 다른 곳에서 내려받은 설치파일을 수동으로 실행하거나 압축을 풀고 경로를 등록해야 한다.

## 3. Custom BLAST database 생성

1. BLAST가 설정된 상태에서 하단 **BLAST** 패널의 **Create Database...** 를 클릭한다.
2. Source FASTA 파일(nucleotide 또는 protein), molecule type(파일 내용으로 자동 추정됨, 필요시 수정), database 이름을 지정한다.
3. **OK**를 누르면 백그라운드에서:
   - sequence ID 중복/문제 문자(`|` 등)를 검사하고, 필요하면 안전한 ID(`seq_000001` 형식)로 바꾸고 원래 ID와의 매핑을 기록한다.
   - `makeblastdb`를 실행한다.
   - `blastdbcmd -info`로 생성된 database를 검증한다.
   - `db_manifest.json`(schema version, database ID, 원본 checksum, sequence 수, ID 매핑 등)을 기록한다.
4. 완료되면 database 목록에 나타나며 이후 BLAST 실행 시 선택할 수 있다.

## 4. Database 목록/위치

Database는 project가 아니라 사용자 전역 폴더에 저장된다: `%LOCALAPPDATA%\GenomeWorkbench\blast\databases\<이름>\`. 여러 project에서 동일한 reference database를 재사용할 수 있다는 뜻이다. Database 목록 자체는 `%LOCALAPPDATA%\GenomeWorkbench\blast\catalog.json`에 기록된다.

이미 적용된 annotation의 BLAST 근거(database 이름, checksum, subject ID, identity, e-value 등)는 project 파일(`.gwbproj`) 안에 별도로 저장되므로, database를 나중에 지우거나 catalog에서 제거해도 과거 annotation의 근거 정보 자체는 project 안에 그대로 남는다.

## 5. BLAST 실행

Genome Map에서 구간을 선택하고 우클릭 → **Run BLAST...**를 선택하면 하단 BLAST 패널에 선택 정보가 채워진다. Program은 query와 database의 분자 종류(nucleotide/protein)에 따라 자동 제안된다(blastn/blastp/blastx/tblastn). e-value, max target sequences, 결과 표시 필터(최소 identity/coverage — 검색 자체가 아니라 표시만 필터링함)를 조정할 수 있다.

## 6. 일반 오류와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| BLAST Setup에서 모든 실행파일이 [MISSING]으로 표시됨 | 경로가 잘못되었거나 PATH에 없음 | `bin` 폴더 경로가 정확한지 확인, 또는 실행파일이 있는 폴더를 직접 지정 |
| "makeblastdb/blastdbcmd are not available" 메시지와 함께 Create Database가 거부됨 | BLAST Setup을 아직 하지 않았거나 해당 실행파일만 없음 | BLAST Setup에서 두 실행파일이 [OK]인지 확인 |
| Run BLAST 시 "X is not available" | 선택한 program(blastn 등)의 실행파일이 없음 | BLAST Setup에서 해당 실행파일 확인 |
| Database 생성이 오래 걸리거나 실패 | 대형 FASTA, 디스크 공간 부족, ID 문제 | 로그 패널(Jobs & Log)에서 상세 오류 확인. ID 문제는 자동으로 안전 ID로 변환되므로 대부분 해결됨 |
| BLAST 결과가 비어 있음 | e-value가 너무 엄격하거나 실제로 유의미한 hit이 없음 | e-value를 완화하거나 다른 database로 시도 |

## 7. 재현성

각 적용된 annotation의 Inspector > Provenance에서 다음을 확인할 수 있다: 사용된 프로그램/버전, database 이름과 checksum, query checksum, 전체 parameter, subject ID, identity/coverage/e-value/bitscore, raw 결과 파일 경로. 동일한 조건으로 재현하려면 이 정보를 그대로 사용하면 된다.
