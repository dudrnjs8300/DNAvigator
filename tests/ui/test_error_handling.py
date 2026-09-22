"""Regression coverage for a real support complaint: users saw a raw
'database is locked' error with no explanation and no clear next step,
because nothing in the app ever installed a sys.excepthook -- an exception
escaping a Qt slot (e.g. a background BLAST job's main-thread completion
handler calling project_service.log_audit) just vanished into PySide6's
default handler, invisible in a windowed build with no console.
"""

from __future__ import annotations

import sqlite3
import sys

import pytest
from PySide6.QtWidgets import QMessageBox

from genome_workbench.infrastructure import error_handling

pytestmark = pytest.mark.ui


@pytest.fixture
def restore_excepthook():
    original = sys.excepthook
    yield
    sys.excepthook = original


def _raise_and_capture(exc: BaseException) -> None:
    try:
        raise exc
    except type(exc):
        sys.excepthook(*sys.exc_info())


def test_database_locked_error_shows_specific_actionable_message(
    qtbot, monkeypatch, restore_excepthook
):
    error_handling.install()
    captured = {}
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(
            lambda *a, **k: captured.setdefault("args", a) or QMessageBox.StandardButton.Ok
        ),
    )

    _raise_and_capture(sqlite3.OperationalError("database is locked"))

    assert "args" in captured
    title, message = captured["args"][1], captured["args"][2]
    assert title == "Project File Locked"
    assert "OneDrive" in message or "network drive" in message


def test_generic_exception_shows_a_visible_message_instead_of_vanishing(
    qtbot, monkeypatch, restore_excepthook
):
    error_handling.install()
    captured = {}
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(
            lambda *a, **k: captured.setdefault("args", a) or QMessageBox.StandardButton.Ok
        ),
    )

    _raise_and_capture(ValueError("something else broke"))

    assert "args" in captured
    title, message = captured["args"][1], captured["args"][2]
    assert title == "Unexpected Error"
    assert "something else broke" in message


def test_unrelated_operational_error_does_not_get_the_locked_message(
    qtbot, monkeypatch, restore_excepthook
):
    error_handling.install()
    captured = {}
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(
            lambda *a, **k: captured.setdefault("args", a) or QMessageBox.StandardButton.Ok
        ),
    )

    _raise_and_capture(sqlite3.OperationalError("no such table: foo"))

    title = captured["args"][1]
    assert title == "Unexpected Error"


def test_keyboard_interrupt_is_not_swallowed(monkeypatch, restore_excepthook):
    error_handling.install()
    calls = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *a: calls.append(a))

    _raise_and_capture(KeyboardInterrupt())

    assert len(calls) == 1


def test_every_unhandled_exception_is_logged(qtbot, monkeypatch, restore_excepthook, caplog):
    error_handling.install()
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    with caplog.at_level("ERROR", logger="genome_workbench"):
        _raise_and_capture(sqlite3.OperationalError("database is locked"))

    assert any("Unhandled exception" in r.message for r in caplog.records)
