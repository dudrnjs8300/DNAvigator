"""Non-UI diagnostics used by both ``--self-test``/``--smoke-test`` CLI flags
and (in later phases) a GUI Diagnostics panel. Exercises the same
application-service layer the GUI calls — no separate fake implementation.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    optional: bool = False


@dataclass(slots=True)
class SelfTestResult:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def core_ok(self) -> bool:
        return all(c.ok for c in self.checks if not c.optional)

    def to_dict(self) -> dict:
        return {
            "core_ok": self.core_ok,
            "checks": [
                {"name": c.name, "ok": c.ok, "detail": c.detail, "optional": c.optional}
                for c in self.checks
            ],
        }


def run_self_test() -> SelfTestResult:
    result = SelfTestResult()
    result.checks.append(_check_writable_user_directory())
    result.checks.append(_check_sqlite())
    result.checks.append(_check_format_codecs())
    result.checks.append(_check_qt_platform_plugin())
    result.checks.append(_check_blast_configured())
    return result


def _check_writable_user_directory() -> CheckResult:
    from genome_workbench.infrastructure.filesystem.paths import app_data_dir

    try:
        directory = app_data_dir()
        probe = directory / ".self_test_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult("writable_user_directory", True, str(directory))
    except OSError as exc:
        return CheckResult("writable_user_directory", False, str(exc))


def _check_sqlite() -> CheckResult:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.execute("SELECT * FROM t")
        conn.close()
        return CheckResult("sqlite", True, f"sqlite3 {sqlite3.sqlite_version}")
    except sqlite3.Error as exc:
        return CheckResult("sqlite", False, str(exc))


def _check_format_codecs() -> CheckResult:
    from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta

    try:
        with tempfile.TemporaryDirectory() as tmp:
            fasta_path = Path(tmp) / "probe.fasta"
            fasta_path.write_text(">probe\nACGTACGT\n", encoding="utf-8")
            parsed = read_fasta(fasta_path)
            if len(parsed.records) != 1:
                return CheckResult(
                    "format_codecs", False, f"expected 1 record, got {len(parsed.records)}"
                )
        return CheckResult("format_codecs", True, "FASTA codec round-trip ok")
    except Exception as exc:  # noqa: BLE001 - self-test must report, not crash
        return CheckResult("format_codecs", False, str(exc))


def _check_qt_platform_plugin() -> CheckResult:
    try:
        from PySide6.QtWidgets import QApplication

        existing = QApplication.instance()
        if existing is not None:
            return CheckResult("qt_platform_plugin", True, "QApplication already running")

        env_backup = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            app = QApplication([])
            app.quit()
            return CheckResult("qt_platform_plugin", True, "offscreen platform plugin loaded")
        finally:
            if env_backup is None:
                os.environ.pop("QT_QPA_PLATFORM", None)
            else:
                os.environ["QT_QPA_PLATFORM"] = env_backup
    except Exception as exc:  # noqa: BLE001
        return CheckResult("qt_platform_plugin", False, str(exc))


def _check_blast_configured() -> CheckResult:
    return CheckResult(
        "blast_executable",
        False,
        "BLAST+ not yet configured (Tool Setup Wizard is Phase 5)",
        optional=True,
    )


@dataclass(slots=True)
class SmokeTestResult:
    steps: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "steps": [{"name": s.name, "ok": s.ok, "detail": s.detail} for s in self.steps],
        }


def run_smoke_test(fixture_dir: Path, output_dir: Path) -> SmokeTestResult:
    from genome_workbench.application.annotation_service import AnnotationService
    from genome_workbench.application.export_service import ExportService, ExportValidationError
    from genome_workbench.application.import_service import ImportService
    from genome_workbench.application.project_service import ProjectService
    from genome_workbench.domain.qualifiers import QualifierSet
    from genome_workbench.infrastructure.formats.semantic_compare import compare_semantic

    result = SmokeTestResult()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    preferred = Path(fixture_dir) / "simple_linear.fasta"
    if preferred.exists():
        fasta_path = preferred
    else:
        fasta_candidates = sorted(Path(fixture_dir).glob("*.fasta")) + sorted(
            Path(fixture_dir).glob("*.fa")
        )
        if not fasta_candidates:
            result.steps.append(
                CheckResult("locate_fixture", False, f"no .fasta/.fa file found in {fixture_dir}")
            )
            return result
        fasta_path = fasta_candidates[0]
    result.steps.append(CheckResult("locate_fixture", True, str(fasta_path)))

    project_path = output_dir / "smoke_test.gwbproj"
    project_path.unlink(missing_ok=True)
    project_service = ProjectService()
    import_service = ImportService(project_service)
    annotation_service = AnnotationService(project_service)
    export_service = ExportService(project_service)

    try:
        project_service.create_new(project_path, "Smoke Test")
        result.steps.append(CheckResult("create_project", True, str(project_path)))

        import_result = import_service.import_fasta(fasta_path)
        result.steps.append(
            CheckResult(
                "import_fasta",
                bool(import_result.records),
                f"{len(import_result.records)} record(s)",
            )
        )
        if not import_result.records:
            return result
        record = import_result.records[0]

        if record.length >= 9:
            end = min(record.length, (record.length // 3) * 3)
            feature = annotation_service.create_simple_feature(
                record, 1, end, 1, "misc_feature", QualifierSet.from_pairs([("note", "smoke test")])
            )
            result.steps.append(
                CheckResult("create_feature", True, f"feature {feature.id} at 1..{end}")
            )
        else:
            result.steps.append(CheckResult("create_feature", True, "skipped (record too short)"))

        project_service.touch()
        project_service.close()
        result.steps.append(CheckResult("save_and_close", True, "closed"))

        project_service.open(project_path)
        reopened_records = project_service.list_records()
        result.steps.append(
            CheckResult(
                "reopen_project",
                len(reopened_records) == len(import_result.records),
                f"{len(reopened_records)} record(s) after reopen "
                f"(expected {len(import_result.records)})",
            )
        )

        features_by_record = {r.id: project_service.list_features(r.id) for r in reopened_records}
        export_path = output_dir / "smoke_test_export.gbk"
        try:
            export_service.export_genbank(reopened_records, features_by_record, export_path)
            result.steps.append(CheckResult("export_genbank", True, str(export_path)))
        except ExportValidationError as exc:
            result.steps.append(CheckResult("export_genbank", False, str(exc)))
            return result

        check_project_path = output_dir / "smoke_test_reimport.gwbproj"
        check_project_path.unlink(missing_ok=True)
        check_project = ProjectService()
        check_import = ImportService(check_project)
        try:
            check_project.create_new(check_project_path, "Smoke Test Reimport")
            reimport_result = check_import.import_genbank(export_path)
            diffs = compare_semantic(
                reopened_records,
                features_by_record,
                reimport_result.records,
                reimport_result.features_by_record_id,
            )
            errors = [d for d in diffs if d.severity == "error"]
            result.steps.append(
                CheckResult(
                    "reimport_semantic_check",
                    not errors,
                    f"{len(errors)} error(s), {len(diffs) - len(errors)} warning(s)",
                )
            )
        finally:
            check_project.close()
    finally:
        project_service.close()

    return result
