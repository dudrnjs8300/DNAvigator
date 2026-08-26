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
