"""Downloads and installs the official NCBI BLAST+ Windows distribution.

Only ever fetches from ftp.ncbi.nlm.nih.gov (NCBI's own distribution site),
resolved dynamically from NCBI's own release index -- never a hardcoded old
version, never a third-party mirror. Windows only: fetches the portable
"x64-win64" .tar.gz build (plain extract, no installer/admin rights
required), verifies it against NCBI's published MD5 checksum before
extracting, and unpacks it under a caller-supplied directory.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tarfile
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_LATEST_INDEX_URL = "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/"
_FILENAME_PATTERN = re.compile(r'href="(ncbi-blast-[\d.]+\+-x64-win64\.tar\.gz)"')
_VERSION_PATTERN = re.compile(r"ncbi-blast-([\d.]+\+)-x64-win64")
_DEFAULT_TIMEOUT_SECONDS = 30.0
_CHUNK_SIZE = 256 * 1024

ProgressCallback = Callable[[int, int], None]  # (bytes_downloaded, total_bytes)


class DownloadCancelled(Exception):
    pass


@dataclass(slots=True)
class ReleaseInfo:
    filename: str
    url: str
    md5_url: str
    version: str


def resolve_latest_windows_release(timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> ReleaseInfo:
    """Find the current NCBI BLAST+ Windows portable-archive filename by
    reading NCBI's own release index page. Raises on any network/parse
    failure -- callers must surface this to the user rather than silently
    falling back to a guessed/hardcoded old version.
    """
    with urllib.request.urlopen(_LATEST_INDEX_URL, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    match = _FILENAME_PATTERN.search(html)
    if match is None:
        raise RuntimeError(f"Could not find a Windows BLAST+ release on {_LATEST_INDEX_URL}")
    filename = match.group(1)
    version_match = _VERSION_PATTERN.search(filename)
    version = version_match.group(1) if version_match else "unknown"
    return ReleaseInfo(
        filename=filename,
        url=_LATEST_INDEX_URL + filename,
        md5_url=_LATEST_INDEX_URL + filename + ".md5",
        version=version,
    )


def _fetch_expected_md5(md5_url: str, timeout: float) -> str:
    with urllib.request.urlopen(md5_url, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    first_token = text.split()[0] if text.split() else ""
    return first_token.strip().lower()


def _download_archive(
    release: ReleaseInfo,
    archive_path: Path,
    cancel_event: threading.Event | None,
    progress_callback: ProgressCallback | None,
    timeout: float,
) -> str:
    """Streams the archive to disk, returns its hex MD5 digest."""
    hasher = hashlib.md5()  # matching NCBI's published MD5 checksum, not used for security
    with urllib.request.urlopen(release.url, timeout=timeout) as response:
        total_bytes = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with open(archive_path, "wb") as f:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise DownloadCancelled("Download cancelled by user")
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
                downloaded += len(chunk)
                if progress_callback is not None:
                    progress_callback(downloaded, total_bytes)
    return hasher.hexdigest()


def download_and_install(
    destination_dir: Path,
    cancel_event: threading.Event | None = None,
    progress_callback: ProgressCallback | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Path:
    """Download the current NCBI BLAST+ Windows portable archive, verify its
    MD5 checksum, and extract it under ``destination_dir``. Returns the path
    to the extracted ``bin`` directory (ready to hand to
    ``detector.detect_installation``). Re-running replaces any previous
    extraction under the same destination.
    """
    release = resolve_latest_windows_release(timeout=timeout)
    expected_md5 = _fetch_expected_md5(release.md5_url, timeout=timeout)

    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_path = destination_dir / release.filename
    try:
        actual_md5 = _download_archive(
            release, archive_path, cancel_event, progress_callback, timeout
        )
        if actual_md5 != expected_md5:
            raise ValueError(
                f"Downloaded archive checksum mismatch (expected {expected_md5}, "
                f"got {actual_md5}) -- download may be corrupt; try again."
            )

        extract_root = destination_dir / release.version.rstrip("+")
        if extract_root.exists():
            shutil.rmtree(extract_root)
        with tarfile.open(archive_path) as tar:
            tar.extractall(extract_root, filter="data")
    finally:
        archive_path.unlink(missing_ok=True)

    # NCBI's archive has a single top-level ncbi-blast-<ver>+/ directory.
    top_level_dirs = [p for p in extract_root.iterdir() if p.is_dir()]
    if len(top_level_dirs) != 1:
        raise RuntimeError(f"Unexpected archive layout under {extract_root}")
    bin_dir = top_level_dirs[0] / "bin"
    if not bin_dir.is_dir():
        raise RuntimeError(f"Extracted archive has no bin/ directory: {bin_dir}")
    return bin_dir
