# 라이선스 정책 (초안 — Phase 8에서 법적 검토와 함께 확정)

## 애플리케이션 자체

- `DNAvigator` 자체 코드는 MIT 라이선스로 배포한다 (`LICENSE` 참고). 확정 전까지는 초안이며, 아래 third-party 조건을 검토한 뒤 최종 확정한다.

## PySide6 / Qt

- PySide6는 LGPLv3(및 상용 라이선스) 조건으로 배포된다. 이 프로젝트는 Qt를 **동적 라이브러리 형태로 유지**하며(PyInstaller onedir 빌드, 정적 링크 아님), 사용자가 Qt 라이브러리를 교체할 수 있는 구조를 유지한다. 이는 LGPLv3의 동적 링크 요건을 만족하기 위함이다.
- 배포 시 `THIRD_PARTY_NOTICES.md`에 Qt/PySide6 라이선스 고지를 포함한다.
- 참고: https://doc.qt.io/qtforpython-6/licenses.html

## Biopython

- Biopython Software License(BSD-3-Clause 유사)로 배포되며 상업적/비상업적 재배포에 제약이 적다. `THIRD_PARTY_NOTICES.md`에 고지문을 포함한다.

## NCBI BLAST+

- **기본 배포본에 BLAST+ 실행파일을 포함하지 않는다.** 재배포 허용 여부에 대한 법적 검토가 완료되기 전까지는 다음 두 경로만 제공한다.
  1. 사용자가 이미 설치한 BLAST+ 경로를 등록 (Phase 5)
  2. Tool Setup Wizard가 NCBI 공식 배포 위치에서 checksum 검증 후 user-local tools directory에 설치 (Phase 5)
- 참고: https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/

## PyInstaller

- PyInstaller bootloader는 GPL 예외 조항이 있는 라이선스로, 생성된 실행파일에 GPL 의무가 전이되지 않는다. 참고: https://pyinstaller.org/en/stable/license.html

## 정책

- GPL 의존성을 Python library로 직접 결합하지 않는다. 외부 executable로 호출하는 도구(BLAST+)와 Python library dependency를 구분한다.
- 새 dependency 추가 전 `pyproject.toml` 및 `docs/DECISIONS.md`에 라이선스/유지보수 상태/Windows wheel 여부를 기록한다.
- code-signing 인증서가 없으므로 배포본을 "signed build"라고 표시하지 않는다. Windows Defender/SmartScreen이 unsigned build에 경고를 표시할 수 있음을 사용자 매뉴얼에 안내한다(Phase 8).
