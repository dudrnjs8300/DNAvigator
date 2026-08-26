"""Tool Setup Wizard auto-download path (KNOWN_LIMITATIONS.md gap): downloads
and extracts the official NCBI BLAST+ Windows distribution.

All tests here run fully offline against a fake urllib.request.urlopen so
the suite stays fast/deterministic/CI-safe -- they exercise the same parsing,
checksum-verification, extraction, and cancellation code paths that run
against the real ftp.ncbi.nlm.nih.gov server, just with canned responses
standing in for the network.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import threading
from pathlib import Path

import pytest

from genome_workbench.infrastructure.blast import downloader

_INDEX_HTML = """
<html><body>
<a href="ncbi-blast-2.17.0+-x64-win64.tar.gz">ncbi-blast-2.17.0+-x64-win64.tar.gz</a>
<a href="ncbi-blast-2.17.0+-x64-win64.tar.gz.md5">md5</a>
<a href="ncbi-blast-2.17.0+-win64.exe">ncbi-blast-2.17.0+-win64.exe</a>
</body></html>
"""


def _build_fake_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in (
            ("ncbi-blast-2.17.0+/bin/blastn.exe", b"fake blastn binary"),
            ("ncbi-blast-2.17.0+/bin/blastx.exe", b"fake blastx binary"),
            ("ncbi-blast-2.17.0+/README", b"readme"),
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


@pytest.fixture
def fake_archive() -> tuple[bytes, str]:
    archive_bytes = _build_fake_archive()
    md5 = hashlib.md5(archive_bytes).hexdigest()
    return archive_bytes, md5


def _install_fake_urlopen(monkeypatch, archive_bytes: bytes, md5_text: str) -> list[str]:
    requested_urls: list[str] = []

    def fake_urlopen(url: str, timeout: float | None = None):
        requested_urls.append(url)
        if url == downloader._LATEST_INDEX_URL:
            return _FakeResponse(_INDEX_HTML.encode())
        if url.endswith(".tar.gz.md5"):
            return _FakeResponse(md5_text.encode())
        if url.endswith(".tar.gz"):
            return _FakeResponse(archive_bytes, headers={"Content-Length": str(len(archive_bytes))})
        raise AssertionError(f"unexpected URL requested: {url}")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", fake_urlopen)
    return requested_urls


def test_resolve_latest_windows_release_parses_index_html(monkeypatch):
    _install_fake_urlopen(monkeypatch, b"", "")
    release = downloader.resolve_latest_windows_release()
    assert release.filename == "ncbi-blast-2.17.0+-x64-win64.tar.gz"
    assert release.version == "2.17.0+"
    assert release.url == downloader._LATEST_INDEX_URL + release.filename
    assert release.md5_url == release.url + ".md5"


def test_download_and_install_extracts_bin_directory(monkeypatch, tmp_path: Path, fake_archive):
    archive_bytes, md5 = fake_archive
    md5_text = f"{md5}  ncbi-blast-2.17.0+-x64-win64.tar.gz\n"
    _install_fake_urlopen(monkeypatch, archive_bytes, md5_text)

    progress_calls: list[tuple[int, int]] = []
    bin_dir = downloader.download_and_install(
        tmp_path / "blast_install",
        progress_callback=lambda done, total: progress_calls.append((done, total)),
    )

    assert bin_dir.name == "bin"
    assert (bin_dir / "blastn.exe").read_bytes() == b"fake blastn binary"
    assert (bin_dir / "blastx.exe").read_bytes() == b"fake blastx binary"
    assert progress_calls, "progress_callback should have been invoked at least once"
    assert progress_calls[-1][0] == len(archive_bytes)
    # the downloaded archive is cleaned up after extraction, only the
    # extracted tree remains
    assert not list((tmp_path / "blast_install").glob("*.tar.gz"))


def test_download_and_install_raises_on_checksum_mismatch(
    monkeypatch, tmp_path: Path, fake_archive
):
    archive_bytes, _correct_md5 = fake_archive
    wrong_md5_text = "0" * 32 + "  ncbi-blast-2.17.0+-x64-win64.tar.gz\n"
    _install_fake_urlopen(monkeypatch, archive_bytes, wrong_md5_text)

    with pytest.raises(ValueError, match="checksum mismatch"):
        downloader.download_and_install(tmp_path / "blast_install")

    # no leftover partial/corrupt archive after a verification failure
    assert not list((tmp_path / "blast_install").glob("*.tar.gz"))


def test_download_and_install_respects_cancel_event(monkeypatch, tmp_path: Path, fake_archive):
    archive_bytes, md5 = fake_archive
    md5_text = f"{md5}  ncbi-blast-2.17.0+-x64-win64.tar.gz\n"
    _install_fake_urlopen(monkeypatch, archive_bytes, md5_text)

    cancel_event = threading.Event()

    def cancel_after_first_chunk(_done: int, _total: int) -> None:
        cancel_event.set()

    with pytest.raises(downloader.DownloadCancelled):
        downloader.download_and_install(
            tmp_path / "blast_install",
            cancel_event=cancel_event,
            progress_callback=cancel_after_first_chunk,
        )


def test_resolve_latest_windows_release_raises_if_no_windows_build_listed(monkeypatch):
    def fake_urlopen(url: str, timeout: float | None = None):
        return _FakeResponse(b"<html><body>no windows build here</body></html>")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="Could not find"):
        downloader.resolve_latest_windows_release()
