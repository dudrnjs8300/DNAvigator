import pytest
from hypothesis import given
from hypothesis import strategies as st

from genome_workbench.domain.coordinates import (
    CoordinateError,
    Interval0,
    display_from_internal,
    internal_from_display,
)


def test_spec_example_101_900():
    start0, end0 = internal_from_display(101, 900)
    assert (start0, end0) == (100, 900)
    assert end0 - start0 == 800


def test_display_from_internal_round_trip_example():
    assert display_from_internal(100, 900) == (101, 900)


def test_rejects_start_below_one():
    with pytest.raises(CoordinateError):
        internal_from_display(0, 10)


def test_rejects_end_before_start():
    with pytest.raises(CoordinateError):
        internal_from_display(10, 5)


def test_interval_length():
    assert Interval0(100, 900).length == 800


def test_interval_overlaps():
    assert Interval0(0, 10).overlaps(Interval0(5, 15))
    assert not Interval0(0, 10).overlaps(Interval0(10, 20))


@given(st.integers(min_value=1, max_value=10_000_000), st.integers(min_value=0, max_value=1000))
def test_display_internal_round_trip_property(start_1based, extra_length):
    end_1based = start_1based + extra_length
    start0, end0 = internal_from_display(start_1based, end_1based)
    back_start, back_end = display_from_internal(start0, end0)
    assert (back_start, back_end) == (start_1based, end_1based)


@given(st.integers(min_value=1, max_value=10_000_000), st.integers(min_value=0, max_value=1000))
def test_internal_length_matches_display_span(start_1based, extra_length):
    end_1based = start_1based + extra_length
    start0, end0 = internal_from_display(start_1based, end_1based)
    assert end0 - start0 == (end_1based - start_1based + 1)
