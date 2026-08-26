from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature
from genome_workbench.ui.rendering.feature_interval_index import FeatureIntervalIndex


def _feature(start0: int, end0: int) -> Feature:
    return Feature(parts=[LocationPart(start0=start0, end0=end0, order_index=0)])


def test_query_overlapping_finds_contained_feature():
    f1 = _feature(100, 200)
    index = FeatureIntervalIndex([f1])
    result = index.query_overlapping(150, 160)
    assert result == [f1]


def test_query_overlapping_excludes_non_overlapping():
    f1 = _feature(100, 200)
    index = FeatureIntervalIndex([f1])
    assert index.query_overlapping(300, 400) == []


def test_query_overlapping_finds_feature_spanning_query_start():
    f1 = _feature(0, 1000)
    index = FeatureIntervalIndex([f1])
    assert index.query_overlapping(500, 600) == [f1]


def test_query_overlapping_boundary_exclusive():
    f1 = _feature(100, 200)
    index = FeatureIntervalIndex([f1])
    assert index.query_overlapping(200, 300) == []
    assert index.query_overlapping(0, 100) == []


def test_rebuild_replaces_contents():
    index = FeatureIntervalIndex([_feature(0, 10)])
    index.rebuild([_feature(1000, 1010)])
    assert index.query_overlapping(0, 10) == []
    assert len(index.query_overlapping(1000, 1010)) == 1


def test_len():
    index = FeatureIntervalIndex([_feature(0, 10), _feature(20, 30)])
    assert len(index) == 2
