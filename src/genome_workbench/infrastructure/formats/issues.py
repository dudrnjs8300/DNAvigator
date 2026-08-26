"""Shared structured import-issue type used by all format adapters."""

from __future__ import annotations

from dataclasses import dataclass


class ImportSeverity:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ImportIssue:
    severity: str
    code: str
    message: str
    record_display_id: str | None = None
