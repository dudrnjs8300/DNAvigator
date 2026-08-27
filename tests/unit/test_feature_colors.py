from pathlib import Path

from genome_workbench.ui.rendering.feature_colors import (
    DEFAULT_COLOR,
    DEFAULT_FEATURE_COLORS,
    feature_color,
    load_color_overrides,
    save_color_overrides,
)


def test_feature_color_uses_default_when_no_override():
    assert feature_color("CDS").name() == DEFAULT_FEATURE_COLORS["CDS"]


def test_feature_color_falls_back_to_default_color_for_unknown_type():
    assert feature_color("some_unknown_type").name() == DEFAULT_COLOR


def test_feature_color_prefers_override_over_default():
    overrides = {"CDS": "#ff0000"}
    assert feature_color("CDS", overrides).name() == "#ff0000"


def test_feature_color_override_works_for_a_type_with_no_default():
    overrides = {"ncRNA": "#00ff00"}
    assert feature_color("ncRNA", overrides).name() == "#00ff00"


def test_load_color_overrides_empty_when_no_file(tmp_path: Path):
    assert load_color_overrides(tmp_path) == {}


def test_save_then_load_round_trip(tmp_path: Path):
    overrides = {"CDS": "#123456", "ncRNA": "#abcdef"}
    save_color_overrides(overrides, tmp_path)

    loaded = load_color_overrides(tmp_path)
    assert loaded == overrides


def test_save_creates_missing_parent_directory(tmp_path: Path):
    nested = tmp_path / "does" / "not" / "exist"
    save_color_overrides({"CDS": "#111111"}, nested)
    assert load_color_overrides(nested) == {"CDS": "#111111"}


def test_load_returns_empty_on_corrupt_file(tmp_path: Path):
    path = tmp_path / "feature_colors.json"
    path.write_text("not valid json", encoding="utf-8")
    assert load_color_overrides(tmp_path) == {}
