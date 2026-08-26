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

## 빠른 시작 (개발 환경)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_dev.ps1
.venv\Scripts\Activate.ps1
python -m genome_workbench
```

## 테스트 / 품질 검사

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

## Windows 실행파일 빌드

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

`dist/GenomeWorkbench/GenomeWorkbench.exe`가 생성되며, 스크립트가 자동으로 packaged
`--self-test`/`--smoke-test`까지 실행해 검증한다.

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
