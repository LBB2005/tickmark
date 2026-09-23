"""Binomial intervals used on every reported rate (ported from the AEO index)."""
from __future__ import annotations

from finbench import stats


def test_wilson_is_bounded_and_contains_the_point():
    interval = stats.wilson(50, 100)
    assert interval.point == 0.5
    assert 0.0 <= interval.low <= 0.5 <= interval.high <= 1.0


def test_zero_and_one_stay_inside_unit_interval():
    assert stats.wilson(0, 20).low == 0.0
    assert stats.wilson(20, 20).high == 1.0


def test_equal_groups_are_inconclusive():
    gap = stats.difference(20, 100, 20, 100)
    assert not gap.excludes_zero()
    assert stats.is_material(20, 100, 20, 100) is False


def test_a_large_gap_is_material():
    assert stats.is_material(80, 100, 20, 100) is True
