"""Tool Setup Wizard auto-download button in BlastSetupDialog. The network
layer is faked exactly like tests/integration/test_blast_downloader.py so
this stays offline/deterministic; it verifies the dialog wiring (confirm
prompt, progress bar, worker thread, dir_edit + re-detect on success, cancel)
around the already-covered download_and_install() logic.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from genome_workbench.infrastructure.blast import downloader
from genome_workbench.ui.dialogs.blast_setup_dialog import BlastSetupDialog

pytestmark = pytest.mark.ui

_INDEX_HTML = """
<html><body>
<a href="ncbi-blast-2.17.0+-x64-win64.tar.gz">ncbi-blast-2.17.0+-x64-win64.tar.gz</a>
</body></html>
"""


def _build_fake_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in (
            ("ncbi-blast-2.17.0+/bin/blastn.exe", b"fake blastn"),
            ("ncbi-blast-2.17.0+/bin/blastp.exe", b"fake blastp"),
            ("ncbi-blast-2.17.0+/bin/blastx.exe", b"fake blastx"),
            ("ncbi-blast-2.17.0+/bin/tblastn.exe", b"fake tblastn"),
            ("ncbi-blast-2.17.0+/bin/makeblastdb.exe", b"fake makeblastdb"),
            ("ncbi-blast-2.17.0+/bin/blastdbcmd.exe", b"fake blastdbcmd"),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._data = data
        self._pos = 0
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _install_fake_urlopen(monkeypatch, archive_bytes: bytes, md5_text: str) -> None:
    def fake_urlopen(url: str, timeout: float | None = None):
        if url == downloader._LATEST_INDEX_URL:
            return _FakeResponse(_INDEX_HTML.encode())
        if url.endswith(".tar.gz.md5"):
            return _FakeResponse(md5_text.encode())
        if url.endswith(".tar.gz"):
            return _FakeResponse(archive_bytes, headers={"Content-Length": str(len(archive_bytes))})
        raise AssertionError(f"unexpected URL requested: {url}")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", fake_urlopen)


def test_download_button_installs_and_redetects(qtbot, tmp_path: Path, monkeypatch):
    archive_bytes = _build_fake_archive()
    md5 = hashlib.md5(archive_bytes).hexdigest()
    _install_fake_urlopen(
        monkeypatch, archive_bytes, f"{md5}  ncbi-blast-2.17.0+-x64-win64.tar.gz\n"
    )
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.tools_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    info_calls = []
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.QMessageBox.information",
        staticmethod(lambda *a, **k: info_calls.append(a)),
    )

    dialog = BlastSetupDialog()
    qtbot.addWidget(dialog)

    dialog._on_download_clicked()
    worker = dialog._download_worker
    assert worker is not None
    with qtbot.waitSignal(worker.succeeded, timeout=10_000):
        pass
    qtbot.wait(50)  # let the queued succeeded-slot invocation run on the UI thread

    # The downloaded/extracted files landing at the expected path, and the
    # dialog re-pointing itself there, is proof the download path actually
    # ran end to end -- unlike is_fully_installed(), which could otherwise
    # come back True on a dev machine that already has BLAST+ on PATH.
    expected_bin_dir = tmp_path / "blast+" / "2.17.0" / "ncbi-blast-2.17.0+" / "bin"
    assert dialog._dir_edit.text() == str(expected_bin_dir)
    assert (expected_bin_dir / "blastn.exe").read_bytes() == b"fake blastn"
    assert (expected_bin_dir / "blastx.exe").read_bytes() == b"fake blastx"
    assert dialog.installation.is_fully_installed()
    assert info_calls, "success message box should have been shown"
    assert dialog._download_button.isEnabled()
    assert not dialog._download_progress.isVisible()


def test_download_declined_confirmation_does_not_start_worker(qtbot, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.tools_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )

    dialog = BlastSetupDialog()
    qtbot.addWidget(dialog)
    dialog._on_download_clicked()

    assert dialog._download_worker is None
    assert dialog._download_button.isEnabled()


def test_cancel_button_stops_the_download(qtbot, tmp_path: Path, monkeypatch):
    archive_bytes = _build_fake_archive()
    md5 = hashlib.md5(archive_bytes).hexdigest()
    _install_fake_urlopen(
        monkeypatch, archive_bytes, f"{md5}  ncbi-blast-2.17.0+-x64-win64.tar.gz\n"
    )
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.tools_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    warning_calls = []
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.blast_setup_dialog.QMessageBox.warning",
        staticmethod(lambda *a, **k: warning_calls.append(a)),
    )

    dialog = BlastSetupDialog()
    qtbot.addWidget(dialog)
    with qtbot.waitExposed(dialog):
        dialog.show()
    dialog._on_download_clicked()
    worker = dialog._download_worker
    assert worker is not None
    assert dialog._download_cancel_button.isVisible()

    dialog._on_download_cancel_clicked()
    with qtbot.waitSignal(worker.failed, timeout=10_000):
        pass
    qtbot.wait(50)

    assert dialog._download_button.isEnabled()
    assert not dialog._download_cancel_button.isVisible()
    # a user-initiated cancel is not an error -- no warning popup for it
    assert not warning_calls
