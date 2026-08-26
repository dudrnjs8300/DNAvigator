"""CLI entry point.

``GenomeWorkbench.exe`` is a GUI application, but it exposes diagnostic and
self-test flags for clean-machine CI and support triage. These call the same
application services the GUI uses — there is no separate "test" code path.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import sqlite3
import sys
from pathlib import Path

from genome_workbench.version import APP_NAME, APP_VERSION, SCHEMA_VERSION


def _attach_console_for_cli_if_frozen() -> None:
    """When packaged as a windowed (no-console) PyInstaller build, CLI flags
    need a console to print to. Attach the parent terminal's console (the one
    the user ran ``GenomeWorkbench.exe --version`` from) instead of forcing a
    console window to always appear (which would violate the "no console
    window on normal launch" requirement).
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if len(sys.argv) <= 1:
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    attach_parent_process = -1
    if kernel32.AttachConsole(attach_parent_process):
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
        sys.stdin = open("CONIN$", encoding="utf-8")  # noqa: SIM115


def _emit(text: str, file_stem: str) -> None:
    """Print best-effort, and always persist to a file.

    A windowed (no-console) frozen build has no stdout to print to unless a
    console was successfully attached (see ``_attach_console_for_cli_if_frozen``);
    attaching can fail in some non-interactive launch contexts even though the
    command itself ran correctly. Writing the same output to a file under the
    app data directory guarantees CI/support-triage callers can always recover
    the result, matching the "diagnostic bundle export" requirement (spec 13.4).
    """
    with contextlib.suppress(AttributeError, OSError):
        print(text)
    try:
        from genome_workbench.infrastructure.filesystem.paths import app_data_dir

        output_path = app_data_dir() / f"{file_stem}.json"
        output_path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def _cmd_version() -> int:
    _emit(f"{APP_NAME} {APP_VERSION}", "last_version_output")
    return 0


def _cmd_diagnostics() -> int:
    info: dict[str, object] = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "schema_version": SCHEMA_VERSION,
        "python_version": sys.version,
        "platform": platform.platform(),
        "sqlite_version": sqlite3.sqlite_version,
    }
    try:
        import PySide6

        info["pyside6_version"] = PySide6.__version__
    except ImportError as exc:
        info["pyside6_version"] = f"unavailable: {exc}"
    try:
        import Bio

        info["biopython_version"] = Bio.__version__
    except ImportError as exc:
        info["biopython_version"] = f"unavailable: {exc}"

    from genome_workbench.infrastructure.filesystem.paths import app_data_dir

    info["app_data_dir"] = str(app_data_dir())
    _emit(json.dumps(info, indent=2), "last_diagnostics_output")
    return 0


def _cmd_self_test() -> int:
    from genome_workbench.diagnostics import run_self_test

    result = run_self_test()
    _emit(json.dumps(result.to_dict(), indent=2), "last_self_test_output")
    return 0 if result.core_ok else 1


def _cmd_smoke_test(fixture_dir: str, output_dir: str) -> int:
    from genome_workbench.diagnostics import run_smoke_test

    result = run_smoke_test(Path(fixture_dir), Path(output_dir))
    _emit(json.dumps(result.to_dict(), indent=2), "last_smoke_test_output")
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    _attach_console_for_cli_if_frozen()
    parser = argparse.ArgumentParser(prog="GenomeWorkbench")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--smoke-test", nargs=2, metavar=("FIXTURE_DIR", "OUTPUT_DIR"))
    args = parser.parse_args(argv)

    if args.version:
        return _cmd_version()
    if args.diagnostics:
        return _cmd_diagnostics()
    if args.self_test:
        return _cmd_self_test()
    if args.smoke_test:
        return _cmd_smoke_test(*args.smoke_test)

    from genome_workbench.app import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
