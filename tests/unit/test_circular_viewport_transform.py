import pytest

from genome_workbench.ui.rendering.circular_viewport_transform import (
    MAX_ZOOM_SCALE,
    MIN_ZOOM_SCALE,
    CircularViewportTransform,
)


def test_default_transform_is_identity():
    t = CircularViewportTransform()
    assert t.zoom_scale == 1.0
    assert t.rotation_degrees == 0.0
    assert t.is_at_default


def test_zoom_in_increases_scale_and_clamps_at_max():
    t = CircularViewportTransform()
    for _ in range(20):
        t = t.zoomed(1.5)
    assert t.zoom_scale == MAX_ZOOM_SCALE


def test_zoom_out_clamps_at_min_and_resets_pan():
    t = CircularViewportTransform(zoom_scale=4.0, pan_x=50.0, pan_y=-30.0)
    for _ in range(20):
        t = t.zoomed(0.5)
    assert t.zoom_scale == MIN_ZOOM_SCALE
    assert t.pan_x == 0.0
    assert t.pan_y == 0.0


def test_rotation_wraps_around_360():
    t = CircularViewportTransform()
    t = t.rotated(350.0).rotated(20.0)
    assert t.rotation_degrees == 10.0


def test_negative_rotation_wraps_to_positive_range():
    t = CircularViewportTransform().rotated(-10.0)
    assert t.rotation_degrees == 350.0


def test_pan_accumulates():
    t = CircularViewportTransform()
    t = t.panned(10.0, 5.0).panned(-3.0, 2.0)
    assert (t.pan_x, t.pan_y) == (7.0, 7.0)


def test_reset_returns_to_identity_regardless_of_state():
    t = CircularViewportTransform(zoom_scale=6.0, rotation_degrees=123.0, pan_x=9.0, pan_y=-9.0)
    assert t.reset() == CircularViewportTransform()


def test_transform_is_immutable_value_type():
    t1 = CircularViewportTransform()
    t2 = t1.zoomed(2.0)
    assert t1.zoom_scale == 1.0
    assert t2.zoom_scale == 2.0


def test_zoom_with_zero_offset_does_not_pan():
    """Zooming exactly on the ring center (the old, pre-anchor behavior)
    must not introduce any pan drift."""
    t = CircularViewportTransform().zoomed(2.0, 0.0, 0.0)
    assert (t.pan_x, t.pan_y) == (0.0, 0.0)


def test_zoom_with_anchor_offset_pans_to_keep_anchor_stationary():
    """Previously zooming always grew the ring around a fixed center, so a
    gene away from dead center would drift toward/off the edge of the
    viewport as you zoomed in on it (user-reported gap: "zoom in 했을 때
    가운데로 확대가 되어버리고 유전자를 볼 수가 없다"). The pan shift after
    zooming with a nonzero anchor offset must follow (1 - factor) * offset
    so the point under the anchor stays under the anchor."""
    t = CircularViewportTransform().zoomed(2.0, 100.0, 50.0)
    assert t.zoom_scale == 2.0
    assert (t.pan_x, t.pan_y) == (-100.0, -50.0)


def test_zoom_anchor_offset_uses_actual_clamped_factor_not_requested_factor():
    """At the zoom limit, the *requested* factor may not be the one that
    actually applies (scale gets clamped) -- using the requested factor for
    the pan-shift math instead of the real one would drift the anchor point
    away from the cursor right at the boundary."""
    t = CircularViewportTransform(zoom_scale=7.0)
    t = t.zoomed(2.0, 100.0, 0.0)  # requests scale 14.0, clamps to MAX (8.0)
    assert t.zoom_scale == MAX_ZOOM_SCALE
    actual_factor = MAX_ZOOM_SCALE / 7.0
    expected_pan_x = (1 - actual_factor) * 100.0
    assert t.pan_x == pytest.approx(expected_pan_x)


def test_zoom_out_to_minimum_still_resets_pan_even_with_anchor_offset():
    t = CircularViewportTransform(zoom_scale=1.2, pan_x=10.0, pan_y=10.0)
    t = t.zoomed(0.1, 100.0, 100.0)  # would clamp to MIN_ZOOM_SCALE
    assert t.zoom_scale == MIN_ZOOM_SCALE
    assert (t.pan_x, t.pan_y) == (0.0, 0.0)
