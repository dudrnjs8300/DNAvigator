from genome_workbench.ui.rendering.viewport_transform import LodLevel, ViewportTransform


def test_whole_genome_view():
    vt = ViewportTransform.whole_genome(10000, 1000)
    assert vt.view_start0 == 0
    assert vt.view_end0 == 10000
    assert vt.bp_per_pixel == 10


def test_genome_to_pixel_and_back():
    vt = ViewportTransform(1000, 2000, 500, 10000)
    x = vt.genome_to_pixel(1500)
    assert x == 250
    assert vt.pixel_to_genome(250) == 1500


def test_lod_level_thresholds():
    assert ViewportTransform(0, 5_000_000, 1000, 5_000_000).lod_level() == LodLevel.OVERVIEW
    assert ViewportTransform(0, 50_000, 1000, 5_000_000).lod_level() == LodLevel.GENE
    assert ViewportTransform(0, 2000, 1000, 5_000_000).lod_level() == LodLevel.FEATURE
    assert ViewportTransform(0, 200, 1000, 5_000_000).lod_level() == LodLevel.BASE


def test_zoomed_in_keeps_anchor_fixed_ish():
    vt = ViewportTransform(0, 10000, 1000, 100000)
    zoomed = vt.zoomed(0.5, anchor_pixel=500)
    assert zoomed.visible_length == 5000
    assert zoomed.view_start0 <= 5000 <= zoomed.view_end0


def test_zoomed_clamped_to_sequence_bounds():
    vt = ViewportTransform(0, 100, 1000, 100)
    zoomed_out = vt.zoomed(5.0, anchor_pixel=50)
    assert zoomed_out.view_start0 == 0
    assert zoomed_out.view_end0 == 100


def test_panned_clamped_at_start():
    vt = ViewportTransform(100, 200, 1000, 10000)
    panned = vt.panned(-500)
    assert panned.view_start0 == 0
    assert panned.visible_length == 100


def test_panned_clamped_at_end():
    vt = ViewportTransform(9900, 10000, 1000, 10000)
    panned = vt.panned(500)
    assert panned.view_end0 == 10000
    assert panned.visible_length == 100


def test_fit_to_range_adds_padding():
    vt = ViewportTransform(0, 10000, 1000, 10000)
    fitted = vt.fit_to_range(1000, 2000, padding_fraction=0.1)
    assert fitted.view_start0 < 1000
    assert fitted.view_end0 > 2000


def test_construction_clamps_end_to_sequence_length():
    vt = ViewportTransform(0, 999999, 1000, 5000)
    assert vt.view_end0 == 5000
