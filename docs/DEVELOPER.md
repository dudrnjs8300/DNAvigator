# 개발자 가이드 (DEVELOPER.md)

이 문서는 DNAvigator 저장소를 직접 수정하거나 빌드하려는 개발자를 위한 것이다.
그냥 프로그램을 설치해서 쓰기만 하려면 [`README.md`](../README.md)만 보면 된다.

## 개발 환경 빠른 시작

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

## Windows 실행파일/인스톨러 직접 빌드

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

`dist/DNAvigator/DNAvigator.exe`가 생성되며, 스크립트가 자동으로 packaged
`--self-test`/`--smoke-test`까지 실행해 검증한다.

인스톨러(.exe)까지 만들려면 [Inno Setup 6](https://jrsoftware.org/isinfo.php)를 설치한 뒤:

```powershell
iscc installer\dnavigator.iss
```

`release/DNAvigator-0.2.0-win-x64-setup.exe`가 생성된다. 자세한 내용은
[`installer/dnavigator.iss`](../installer/dnavigator.iss)와
[`docs/RELEASE_TEST_REPORT.md`](RELEASE_TEST_REPORT.md) 참고.

## 진단 CLI

GUI 프로그램이지만 CI/장애 진단을 위해 command-line option을 제공한다(GUI와 동일한 application
service를 사용한다):

```
DNAvigator.exe --version
DNAvigator.exe --diagnostics
DNAvigator.exe --self-test
DNAvigator.exe --smoke-test <fixture-directory> <output-directory>
```

## 릴리스 절차

`v*` 형식의 태그(예: `v0.2.0`)를 push하면 `.github/workflows/windows-release.yml`이 자동으로:

1. 품질 게이트(ruff/mypy/pytest)를 통과시키고
2. PyInstaller onedir 빌드 + packaged self-test/smoke-test를 clean `windows-latest` 러너에서 실행하고
3. portable ZIP과 Inno Setup 인스톨러를 만들고, 그 인스톨러로 실제 silent 설치 → self-test → 시작 메뉴
   바로가기 확인 → silent 제거까지 검증한 뒤
4. GitHub Release를 만들어 두 산출물을 첨부한다.

```powershell
git tag v0.2.0
git push origin v0.2.0
```

`workflow_dispatch`로 태그 없이 수동 실행하면 1~3단계까지만 하고 Release는 만들지 않는다(빌드
자체를 미리 확인하고 싶을 때 사용).

## 관련 문서

- 전체 로드맵: [`docs/PRODUCT_SPEC.md`](PRODUCT_SPEC.md)
- 진행 상황: [`PROGRESS.md`](../PROGRESS.md)
- 알려진 제한/설계 결정: [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md), [`docs/DECISIONS.md`](DECISIONS.md)
- 릴리스 검증 기록: [`docs/RELEASE_TEST_REPORT.md`](RELEASE_TEST_REPORT.md), [`docs/PERFORMANCE.md`](PERFORMANCE.md)
- 라이선스: [`../LICENSE`](../LICENSE), [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md), [`docs/LICENSING.md`](LICENSING.md)
