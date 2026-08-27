"""CLI argument parsing in genome_workbench.__main__.

Previously untested: a bare project-path argument (exactly what Windows
passes as %1 when a .gwbproj file is double-clicked via the file association
the installer sets up) was not accepted by argparse at all -- main() would
exit with an "unrecognized arguments" error instead of opening the project,
so double-clicking a project file crashed the app immediately
(KNOWN_LIMITATIONS.md gap: file association was registered but never
actually wired to open the file).
"""

from __future__ import annotations

from genome_workbench import __main__ as cli


def test_project_path_argument_launches_gui_with_that_path(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_app(argv=None, open_project_path=None):
        captured["argv"] = argv
        captured["open_project_path"] = open_project_path
        return 0

    monkeypatch.setattr("genome_workbench.app.run_app", fake_run_app)

    exit_code = cli.main(["C:\\Users\\someone\\my_project.gwbproj"])

    assert exit_code == 0
    assert captured["open_project_path"] == "C:\\Users\\someone\\my_project.gwbproj"


def test_no_arguments_launches_gui_with_no_project_path(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "genome_workbench.app.run_app",
        lambda argv=None, open_project_path=None: (
            captured.update(open_project_path=open_project_path) or 0
        ),
    )

    exit_code = cli.main([])

    assert exit_code == 0
    assert captured["open_project_path"] is None


def test_version_flag_does_not_launch_gui(monkeypatch, capsys):
    called = False

    def fake_run_app(argv=None, open_project_path=None):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr("genome_workbench.app.run_app", fake_run_app)
    monkeypatch.setattr(cli, "_attach_console_for_cli_if_frozen", lambda: None)

    exit_code = cli.main(["--version"])

    assert exit_code == 0
    assert called is False


def test_self_test_flag_does_not_launch_gui(monkeypatch):
    called = False

    def fake_run_app(argv=None, open_project_path=None):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr("genome_workbench.app.run_app", fake_run_app)
    monkeypatch.setattr(cli, "_attach_console_for_cli_if_frozen", lambda: None)

    cli.main(["--self-test"])

    assert called is False
