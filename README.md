# GenomeWorkbench

로컬(offline) Windows 데스크톱용 genome sequence visualization 및 annotation workbench.
FASTA/GenBank/GFF3 계열 파일을 열어 sequence와 annotation을 보고, 수동 또는 로컬 BLAST 근거로
annotation을 추가·수정한 뒤 표준 형식으로 내보낼 수 있다. 사용자의 sequence/annotation을
외부 서버로 전송하지 않는다.

> **개발 상태**: Phase 1 (FASTA → 수동 annotation → project → GenBank export/reimport 수직 슬라이스) 완료.
> 전체 로드맵은 [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md), 현재 진행 상황은 [`PROGRESS.md`](PROGRESS.md) 참고.

## 현재 지원 기능 (Phase 1 기준)

- Nucleotide/protein FASTA import (gzip 지원, 확장자 무관 sniffing)
- GenBank import/export (single/multi-record, compound/reverse-strand location, unknown qualifier 보존)
- 수동 feature 생성 (좌표/strand/type/qualifier, translation preview, validation)
- Project 저장/재오픈 (SQLite 기반 `.gwbproj`)
- Undo/redo
- Export 전/후 semantic round-trip 검증, atomic write (원본 파일 보호)
- 진단용 CLI: `--version`, `--diagnostics`, `--self-test`, `--smoke-test`

아직 없는 기능은 [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md)에 정리되어 있다
(GFF3, genome map 시각화, BLAST, autosave/recovery 등은 이후 phase).

## 설치 (일반 사용자)

Python이나 개발 도구 설치 없이, 인스톨러 하나로 설치해서 쓸 수 있다.

1. GitHub Actions의 최신 `windows-release` 실행 결과에서 **`GenomeWorkbench-installer`** artifact를 내려받는다
   (저장소의 **Actions** 탭 → 가장 최근 `windows-release` 실행 → Artifacts).
2. 압축을 풀면 나오는 `GenomeWorkbench-X.Y.Z-win-x64-setup.exe`를 실행한다.
   - 관리자 권한이 필요 없다(사용자 계정 안에만 설치됨).
   - 코드 서명 인증서가 없어 Windows Defender/SmartScreen이 경고를 띄울 수 있다 — "추가 정보" → "실행"으로 진행하면 된다(`docs/LICENSING.md` 참고).
3. 설치 후 시작 메뉴에서 GenomeWorkbench를 실행한다.

이 설치 파일은 CI(`windows-release.yml`)에서 매번 실제로 빌드되고, 처음부터 아무것도 설치되어 있지 않은
clean Windows 러너에서 실제로 silent 설치 → `--self-test` → 시작 메뉴 바로가기 확인 → silent 제거까지
자동으로 검증된 뒤에만 artifact로 올라간다.

BLAST 검색 기능을 쓰려면 NCBI BLAST+가 별도로 필요하지만, 앱 내 **BLAST > BLAST Setup...** 대화상자에서
"Download & Install BLAST+" 버튼으로 자동 설치할 수 있다(`docs/BLAST_SETUP.md` 참고).

## 개발자용: 소스에서 실행/빌드

아래는 이 저장소를 직접 수정하거나 기여하려는 개발자를 위한 절차다. 그냥 프로그램을 쓰기만 하려면
위 "설치 (일반 사용자)"만 보면 된다.

### 개발 환경 빠른 시작

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_dev.ps1
.venv\Scripts\Activate.ps1
python -m genome_workbench
```

### 테스트 / 품질 검사

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_checks.ps1
```

개별 실행:

```powershell
python -m ruff format --check src tests
python -m ruff check src tests
python -m mypy src/genome_workbench
$env:QT_QPA_PLATFORM = "offscreen"; python -m pytest tests -q
```

### Windows 실행파일/인스톨러 직접 빌드

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

`dist/GenomeWorkbench/GenomeWorkbench.exe`가 생성되며, 스크립트가 자동으로 packaged
`--self-test`/`--smoke-test`까지 실행해 검증한다.

인스톨러(.exe)까지 만들려면 [Inno Setup 6](https://jrsoftware.org/isinfo.php)를 설치한 뒤:

```powershell
iscc installer\genome_workbench.iss
```

`release/GenomeWorkbench-0.1.0-win-x64-setup.exe`가 생성된다. 자세한 내용은
[`installer/genome_workbench.iss`](installer/genome_workbench.iss)와 `docs/RELEASE_TEST_REPORT.md` 참고.

## 진단 CLI

GUI 프로그램이지만 CI/장애 진단을 위해 command-line option을 제공한다(GUI와 동일한 application
service를 사용한다):

```
GenomeWorkbench.exe --version
GenomeWorkbench.exe --diagnostics
GenomeWorkbench.exe --self-test
GenomeWorkbench.exe --smoke-test <fixture-directory> <output-directory>
```

## License

MIT (`LICENSE`). Third-party dependency license는 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md),
BLAST+ 재배포 정책은 [`docs/LICENSING.md`](docs/LICENSING.md) 참고.
