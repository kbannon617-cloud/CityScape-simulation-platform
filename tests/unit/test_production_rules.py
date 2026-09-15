"""Unit tests for calculate_staffed_building_count - pure math, no database."""

import pytest

from cinis.rules.production_rules import calculate_staffed_building_count


def test_zero_workers_per_building_is_never_labor_limited():
    assert calculate_staffed_building_count(
        total_count=5, workers_per_building=0, available_labor=0
    ) == 5


def test_full_labor_staffs_all_buildings():
    assert calculate_staffed_building_count(
        total_count=3, workers_per_building=5, available_labor=100
    ) == 3


def test_limited_labor_caps_staffed_count():
    # 12 available / 5 per building = floor(2.4) = 2, capped further by total_count=3 -> 2
    assert calculate_staffed_building_count(
        total_count=3, workers_per_building=5, available_labor=12
    ) == 2


def test_zero_available_labor_staffs_zero_buildings():
    assert calculate_staffed_building_count(
        total_count=3, workers_per_building=5, available_labor=0
    ) == 0


def test_exact_labor_match():
    assert calculate_staffed_building_count(
        total_count=4, workers_per_building=5, available_labor=20
    ) == 4


def test_negative_total_count_raises():
    with pytest.raises(ValueError):
        calculate_staffed_building_count(total_count=-1, workers_per_building=5, available_labor=10)


def test_negative_workers_per_building_raises():
    with pytest.raises(ValueError):
        calculate_staffed_building_count(total_count=3, workers_per_building=-1, available_labor=10)


def test_negative_available_labor_raises():
    with pytest.raises(ValueError):
        calculate_staffed_building_count(total_count=3, workers_per_building=5, available_labor=-1)
