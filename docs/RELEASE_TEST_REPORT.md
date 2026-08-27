# Release Test Report

작성일: 2026-08-26
버전: 0.1.0
검증 환경: 개발 머신(Windows 10.0.19045 x64, Python 3.14.6), 자동화 테스트 스위트, 실제 PyInstaller onedir 빌드, 실제 NCBI BLAST+ 2.17.0(win64) 설치
검증하지 못한 것은 "검증하지 못함"이라고 명시한다 — 통과로 보고하지 않는다.

## 요약

- 자동화 테스트: **192 passed**, 0 failed (`pytest tests -q`, `QT_QPA_PLATFORM=offscreen`; 실제 BLAST+ 테스트 2건 포함, BLAST+ 미설치 환경에서는 자동 skip)
- `ruff format --check`, `ruff check`, `mypy src/genome_workbench`: 모두 clean
- Windows 실행파일(onedir) 빌드 성공, `--self-test`/`--smoke-test` exit code 0
- Portable ZIP: 별도 임시 경로 및 한글/공백 경로로 압축 해제 후 `--self-test` exit code 0 확인
- Installer: Inno Setup 6로 컴파일 성공, silent 설치(관리자 권한 불필요) → `--self-test`/`--smoke-test` → Start Menu 바로가기 확인 → silent 제거까지 이 개발 머신에서 검증. 패키징된 exe 자체는 GitHub Actions의 clean `windows-latest` 러너에서도 별도로 검증됨. **installer의 완전히 별도인 clean Windows 계정/VM 설치 검증만 아직 하지 못함** (AT-10 참고)
- GitHub Actions: `test.yml`(품질 게이트)과 `windows-release.yml`(실제 빌드+패키징+clean 러너 exe 검증) 모두 실제로 push/실행해 통과 확인(`https://github.com/dudrnjs8300/genome-workbench`)
- 실제 NCBI BLAST+ 2.17.0(win64) 바이너리: 공식 NCBI FTP에서 설치(MD5 확인)해 blastn/blastp/database 생성/좌표 매핑/annotation 적용까지 실제로 검증(아래 AT-06/AT-07 참고). 대역(mock) 실행파일 기반 테스트도 회귀 검증용으로 계속 유지.

## AT-01 FASTA manual annotation round-trip

**통과.** `tests/integration/test_scenario_a_end_to_end.py`(서비스 계층), `tests/ui/test_main_window_smoke.py::test_new_project_import_fasta_add_feature_save_reopen`(UI). FASTA import → CDS 101..900 생성(gene/product/note/transl_table) → project 저장·재오픈 → 값 유지 확인 → GenBank export → 새 project에서 재수입 → canonical sequence/feature/qualifier 동일 확인. Undo/redo도 별도로 검증됨.

## AT-02 reverse-strand CDS

**통과.** `tests/integration/test_genbank_adapter.py::test_at02_reverse_strand_cds_round_trip`. Reverse strand CDS 생성 → 표시된 nucleotide가 reverse complement인지, translation이 생물학적 방향으로 계산되는지, GBK export–reimport 후 checksum 동일한지 확인.

## AT-03 circular origin

**통과 (undo/redo는 별도 검증).** `tests/integration/test_fixtures_import_all.py::test_circular_origin_gbk_extraction_matches_source`로 origin-spanning CDS의 import/추출/생물학적 서열이 정확함을 확인. Linear/circular map에서의 시각적 선택은 `tests/ui/test_genome_visualization_workflow.py`의 feature 클릭 테스트로 (다른 fixture 대상) 검증되었으나, circular_origin.gbk를 UI로 직접 열어 클릭·좌표 수정·undo/redo까지 수행하는 단일 e2e 테스트는 없다 — 기능 자체(좌표 수정, undo/redo)는 다른 시나리오에서 검증되었고 circular origin 데이터 처리도 별도로 검증되었으므로 조합 리스크는 낮다고 판단하나, 완전히 동일한 조합의 자동 테스트는 아니다.

## AT-04 unknown qualifiers

**통과.** `tests/integration/test_genbank_adapter.py::test_unknown_qualifiers_preserved`. 알 수 없는 custom qualifier와 multi-value qualifier(`db_xref` 2개)가 export–reimport 후에도 순서와 값 그대로 보존됨을 확인.

## AT-05 GFF3 pairing

**통과.** `tests/integration/test_fixtures_import_all.py::test_annotation_only_gff3_pairs_with_matching_fna`, `test_unmatched_seqid_reported_when_no_sequence_available`, `tests/integration/test_gff3_service_integration.py`. Annotation-only GFF3 + 별도 FASTA 페어링, 불일치 seqid가 추정 적용 없이 issue로 보고됨을 확인. UI 흐름(불일치 시 FASTA 선택 프롬프트)은 `MainWindow._on_import_gff3`에 구현되어 있으나 이 특정 대화상자 흐름의 UI 자동 테스트는 없음(서비스 계층 로직은 검증됨).

## AT-06 custom nucleotide BLAST DB

**통과 — 실제 BLAST+로 검증됨.** `tests/integration/test_blast_pipeline.py::test_create_database_with_mock_makeblastdb`가 안전하지 않은 ID(`|` 포함) → safe ID 매핑 → manifest 생성 → `blastdbcmd -info` 검증까지의 코드 경로를 대역 실행파일로 계속 확인한다. 여기에 더해 `tests/integration/test_blast_real_installation.py::test_real_blastn_self_hit_and_apply_as_annotation`이 **실제 NCBI BLAST+ 2.17.0**(공식 NCBI FTP에서 설치, MD5 확인됨)으로 동일한 시나리오를 재현한다: 실제 `makeblastdb`로 `simple_linear.fasta`에서 database 생성 → 실제 `blastn`으로 자기 자신의 300bp 조각 검색(identity/coverage 100%) → genome 좌표로 매핑 → annotation 적용까지 전부 실제 바이너리로 통과.

## AT-07 protein BLAST annotation

**통과 — blastn UI e2e + blastp 실제 바이너리 검증.** `tests/ui/test_genome_visualization_workflow.py::test_blast_run_and_apply_hit_as_annotation_end_to_end`가 UI 계층에서 선택 영역 BLAST 실행 → hit 선택 → `product`는 제외하고 `note`만 선택해 적용 → 적용 후 origin locus_tag/protein_id가 복사되지 않음(체크박스 기본값이 그렇게 설계됨)까지 검증한다(blastn 경로). 여기에 더해 `tests/integration/test_blast_real_installation.py::test_real_blastp_self_hit`이 **실제 blastp**로 protein database 생성 → protein 검색 → 정확한 top hit(자기 자신)까지 서비스 계층에서 검증한다. 남은 gap: UI 계층(dispatch/dialog)에서 blastp를 직접 구동하는 자동 테스트는 여전히 blastn 경로만 있다 — program 값과 무관하게 동일한 UI 코드 경로를 타므로 위험은 낮다고 판단하나, 완전히 동일한 조합의 UI 자동 테스트는 아니다.

## AT-08 cancel and failure

**통과.** BLAST 실행 실패(예: 잘못된 database 경로, 실행파일 없음)는 `CallableWorker.failed` 신호 → `QMessageBox.critical`로 안전하게 처리되며 project가 손상되지 않는다. **Cancel UI를 새로 구현했다**: BLAST 패널의 "Cancel Job" 버튼이 `threading.Event`를 서비스 계층까지 전달하고, `infrastructure/blast/runner.py`가 `subprocess.run`(한 번 호출하면 끝날 때까지 끊을 수 없음) 대신 `subprocess.Popen`을 0.2초 간격으로 폴링하는 방식으로 바뀌어 취소 요청 시 실제 프로세스를 즉시 `kill()`한다. `tests/unit/test_blast_runner_cancel.py`가 실제 자식 프로세스(30초 sleep)를 spawn해 취소가 5초 이내(대부분 1초 이내)로 실제로 죽이는지 확인하고, `tests/ui/test_callable_worker_cancel.py`가 worker↔UI 배선을 확인한다. 취소된 job은 에러 대화상자 대신 로그에 기록된다. 부수적으로, 실행 중 새 BLAST job을 중복 시작하는 것도 이제 막힌다(이전에는 막지 않았음).

## AT-09 atomic export

**통과.** `tests/unit/test_atomic_write.py` 5건: 기존 유효 파일이 있는 상태에서 write 콜백이 강제로 실패했을 때 destination이 byte-identical하게 보존됨, temp 파일이 남지 않음, 성공 시에는 정상 교체됨, 상위 디렉터리 자동 생성을 확인.

## AT-10 Windows clean-machine

**부분 검증 — installer는 이 개발 머신에서, 패키징된 exe는 GitHub Actions의 진짜 clean 러너에서 검증됨. installer 자체의 완전히 별도인 clean 계정/VM 설치 검증만 아직 없음.** 이번 세션에서 다음을 실제로 수행했다:
- `iscc installer\genome_workbench.iss`로 installer(`DNAvigator-0.1.0-win-x64-setup.exe`) 컴파일 성공.
- `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LANG=english`로 silent 설치 — `PrivilegesRequired=lowest` 설정대로 관리자 권한 없이 `%LOCALAPPDATA%\Programs\DNAvigator`에 설치됨.
- 설치된 실행파일의 `--self-test`/`--smoke-test` 모두 exit code 0, Start Menu 바로가기(`DNAvigator.lnk`) 생성 확인.
- `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`로 silent 제거 — 설치 디렉터리와 바로가기가 깨끗하게 제거됨을 확인(사용자 데이터는 애초에 설치 디렉터리 밖에 있어 영향 없음).
- (참고) 언어를 2개 이상 등록하면 `/VERYSILENT`만으로는 언어 선택 대화상자가 떠서 자동화 설치가 멈춘다 — `/LANG=`을 함께 지정해야 한다. 대화형(GUI) 설치에서는 해당되지 않는 제약이다.
- `--self-test`의 `blast_executable` 항목은 실제 탐지를 하지 않는 정적 안내 필드이며 `optional: true`로 표시되어 core 실패를 유발하지 않는다 — 이는 실제 NCBI BLAST+ 설치 여부와 무관하게(이 머신에는 이후 실제로 BLAST+를 설치했다) 동일하게 동작함을 확인.
- Portable ZIP을 완전히 다른 임시 경로(및 한글/공백 경로)에 압축 해제해 `--self-test`를 확인 — "이 실행파일 자체가 별도 Python 설치 없이 독립 실행됨"도 검증됨.
- **GitHub Actions의 `windows-latest` 러너에서 패키징된 exe를 실제로 실행해 검증함** — 이 러너는 이 개발 머신과 달리 Python/BLAST/기타 개발 도구가 전혀 미리 설치되어 있지 않은 진짜 clean 환경이다(`https://github.com/dudrnjs8300/genome-workbench/actions/runs/32968044295`). PyInstaller로 처음부터 빌드 → 패키징된 `DNAvigator.exe --self-test`/`--smoke-test` 모두 exit code 0, portable ZIP artifact 업로드까지 확인. 첫 실행 시도에서는 stdout/stderr가 전혀 캡처되지 않고 원인 불명으로 실패했는데, pwsh에서 `.\exe args`로 직접 호출하는 대신 `Start-Process -RedirectStandardOutput/-RedirectStandardError`로 명시적 리다이렉트하도록 바꾸자 재실행에서 정상 통과했다(D-005의 console 부착 취약성과 같은 계열로 추정). 이 발견은 실제 사용자가 GUI로 더블클릭 실행할 때는 해당되지 않지만(콘솔 붙임 로직은 CLI 플래그가 있을 때만 동작), 향후 CLI 자동화(스크립트/CI)에서 이 exe를 호출할 때는 참고할 것.

여전히 남은 것: **완전히 새로운 Windows 사용자 계정 또는 clean VM에서의 installer(.exe) 설치/제거 검증**(위 GitHub Actions 검증은 portable exe만 다루고 installer는 다루지 않는다), 그리고 BLAST Setup Wizard를 통한 실제 BLAST+ 인식 노출 확인.

## 결론

P0 Definition of Done(spec 18절) 대부분이 자동화 테스트와 실제 빌드로 뒷받침되며, 이번 갱신으로 installer의 설치/실행/제거, BLAST 파이프라인(blastn/blastp) 실제 바이너리 검증, BLAST job 취소 UI, 그리고 GitHub Actions 실제 실행(clean 러너에서의 패키징 exe 검증 포함)까지 모두 실증되었다. 다음은 여전히 미완/미검증 상태이며 "완성"이라고 보고하지 않는다:
- 완전히 별도의 clean Windows 사용자 계정/VM에서의 **installer(.exe)** 설치 검증(패키징된 exe 자체는 GitHub Actions clean 러너에서 검증됨 — installer만 남음)
- blastp 경로의 UI 계층(dispatch/dialog) 전용 자동 테스트(서비스 계층은 실제 바이너리로 검증됨)

## 업데이트 (2026-08-27)

이 보고서 작성 이후 다음 두 항목이 추가로 검증/구현되어 결론을 갱신한다(이 시점 이전 섹션의 나머지 내용과 "192 passed" 수치는 작성 당시 스냅샷 그대로 남겨둔다):

- **blastx/tblastn(번역 검색) frame 좌표 매핑을 실제 바이너리로 검증 완료.** `tests/integration/test_blast_real_installation.py`에 실제 `blastx`(뉴클레오타이드 query → protein database)와 실제 `tblastn`(protein query → 뉴클레오타이드 database) 테스트를 추가했다. 표준 유전암호로 알려진 단백질 서열을 프레임 0으로 손수 역번역한 뉴클레오타이드 fixture를 사용하고(프로젝트 자체의 `translate()`로 왕복 검증), 두 프로그램 모두 identity ≥99%의 정확한 top hit을 반환함을 확인했다. 이제 blastn/blastp/blastx/tblastn 4개 프로그램 모두 실제 NCBI BLAST+ 2.17.0으로 검증됨.
- **Tool Setup Wizard에 공식 배포판 자동 다운로드 경로를 구현했다.** `infrastructure/blast/downloader.py`가 NCBI의 release index를 동적으로 읽어 최신 Windows 이식용 배포판(`x64-win64.tar.gz`)을 찾고, MD5 체크섬을 검증한 뒤 `%LOCALAPPDATA%/DNAvigator/tools`에 압축을 푼다. `BlastSetupDialog`에 확인 대화상자·진행률 표시·취소를 갖춘 다운로드 버튼을 연결했다. 네트워크 계층은 fake `urlopen`으로 오프라인 검증(`tests/integration/test_blast_downloader.py` 5건, `tests/ui/test_blast_setup_download.py` 3건); NCBI 서버와의 실제 URL/체크섬 해석 가능 여부는 수동으로 별도 확인했으나(curl로 index/md5 응답 확인), 143MB 전체 다운로드까지 자동화 스위트에서 매번 받지는 않는다(느리고 네트워크 의존적이므로 의도적으로 제외).
- **AT-10의 남은 절반(installer 자체의 clean 환경 검증)을 CI에 편입하고 실제로 통과를 확인했다.** `windows-release.yml`에 Inno Setup 컴파일 → silent 설치 → 설치된 위치에서 `--self-test` → 시작 메뉴 바로가기 확인 → silent 제거까지 자동으로 수행하는 단계를 추가했다(빌드된 `setup.exe`는 `DNAvigator-installer` artifact로 업로드됨). `https://github.com/dudrnjs8300/genome-workbench/actions/runs/33012146083`(windows-release #3)에서 실제로 실행해 4분 58초 만에 전체 성공, `DNAvigator-installer`(42.1MB)와 `DNAvigator-windows-x64`(62.5MB) 두 artifact가 모두 생성됨을 확인했다. 이 러너는 이 개발 머신과 달리 아무것도 미리 설치되어 있지 않은 진짜 clean 환경이므로, "완전히 별도의 clean Windows 환경에서의 installer 설치/실행/제거 검증"이라는 AT-10의 요구를 (영구적인 별도 사용자 계정/VM은 아니지만) 매 릴리스마다 자동으로 반복 검증하는 형태로 충족한다. 남은 것은 File association(`.gwbproj`) 자체의 GUI 수동 확인뿐이다.
- **`AttachConsole` CLI 출력 경로를 실제 cmd.exe/PowerShell에서 검증하다가 실제 버그를 발견해 고쳤다** — 자세한 원인과 수정 내용은 `docs/DECISIONS.md` D-005 참고. 요약: 표준출력이 파일/파이프로 리다이렉션되어 있어도 무조건 콘솔 화면 버퍼에 다시 연결해버려 리다이렉션 대상이 항상 빈 채로 남는 문제였다(exit code는 0이라 실패로 드러나지 않음). `GetFileType`으로 이미 리다이렉션된 핸들인지 먼저 확인하도록 고쳐 cmd.exe 파일 리다이렉션과 PowerShell 파이프 모두에서 실제 텍스트가 잡히는 것을 재빌드한 exe로 직접 확인했다. `--self-test`/`--smoke-test`는 회귀 없이 그대로 통과.
- **Circular map pan(Shift+드래그)을 구현했다.** 상태 클래스(`CircularViewportTransform.panned()`)는 이미 있었지만 마우스 제스처가 연결되어 있지 않았다 — 이제 빈 배경에서 Shift를 누른 채 드래그하면 이동한다(linear canvas의 Shift+휠=pan 관례와 동일). `tests/ui/test_circular_map_zoom_rotation.py`에 회귀 테스트 추가.
- **Record topology(linear/circular) 변경을 undo/redo 가능하게 했다.** 이전에는 `ProjectService.set_record_topology`가 undo stack을 거치지 않는 단순 mutation이라 실수로 바꾸면 되돌릴 방법이 반대로 다시 바꾸는 것뿐이었다. `RecordTopologyChangeCommand`를 추가해 다른 mutation과 동일하게 Ctrl+Z/Y로 되돌릴 수 있다. `tests/integration/test_project_service_records_and_folders.py`, `tests/ui/test_genome_visualization_workflow.py`로 검증.
- **blastp UI 계층(dispatch) 자동 테스트를 추가해 위 "남은 것" 항목을 닫았다.** `tests/fixtures/fake_blast/blastp.bat`를 추가하고, 기존 blastn e2e UI 테스트와 동일한 구조로 protein database 생성 → blastp 실행 → hit 적용까지 UI 코드 경로로 검증하는 테스트를 추가했다.
- **`.gwbproj` file association을 실제로 검증하다가 실제 크래시 버그를 발견해 고쳤다.** 레지스트리 연결은 정확했지만, Windows가 파일 연결 실행 시 넘기는 `%1`(project 경로)을 앱이 전혀 처리하지 않아 `argparse`가 "unrecognized arguments"로 즉시 종료시켰다 — 더블클릭하면 앱이 바로 죽는 상태였다. `__main__.py`/`app.py`/`MainWindow.open_project_at_path`를 연결해 고쳤다. 자세한 내용은 `docs/KNOWN_LIMITATIONS.md` 참고.
