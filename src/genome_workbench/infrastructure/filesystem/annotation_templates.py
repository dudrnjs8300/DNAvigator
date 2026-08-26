"""User-global annotation templates: a saved (feature type + qualifiers)
preset a user can re-apply when creating new features, instead of retyping
the same gene/product/transl_table combination every time.

Stored at ``%LOCALAPPDATA%/GenomeWorkbench/annotation_templates.json``,
scoped to the user rather than a single project -- the same rationale as the
BLAST database catalog (D-007): a template like "bacterial CDS" is useful
across every project, not just the one it was first saved in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from genome_workbench.infrastructure.filesystem.paths import app_data_dir


@dataclass(slots=True)
class AnnotationTemplate:
    name: str
    feature_type: str = "CDS"
    gene: str = ""
    product: str = ""
    note: str = ""
    transl_table: str = "11"
    extra_qualifiers: list[tuple[str, str]] = field(default_factory=list)


def templates_path(directory: Path | None = None) -> Path:
    return (directory or app_data_dir()) / "annotation_templates.json"


def load_templates(directory: Path | None = None) -> list[AnnotationTemplate]:
    path = templates_path(directory)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    templates = []
    for entry in raw:
        templates.append(
            AnnotationTemplate(
                name=entry["name"],
                feature_type=entry.get("feature_type", "CDS"),
                gene=entry.get("gene", ""),
                product=entry.get("product", ""),
                note=entry.get("note", ""),
                transl_table=entry.get("transl_table", "11"),
                extra_qualifiers=[tuple(pair) for pair in entry.get("extra_qualifiers", [])],
            )
        )
    return templates


def save_templates(templates: list[AnnotationTemplate], directory: Path | None = None) -> None:
    path = templates_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "name": t.name,
            "feature_type": t.feature_type,
            "gene": t.gene,
            "product": t.product,
            "note": t.note,
            "transl_table": t.transl_table,
            "extra_qualifiers": [list(pair) for pair in t.extra_qualifiers],
        }
        for t in templates
    ]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_template(template: AnnotationTemplate, directory: Path | None = None) -> None:
    templates = [t for t in load_templates(directory) if t.name != template.name]
    templates.append(template)
    templates.sort(key=lambda t: t.name)
    save_templates(templates, directory)


def delete_template(name: str, directory: Path | None = None) -> None:
    templates = [t for t in load_templates(directory) if t.name != name]
    save_templates(templates, directory)
