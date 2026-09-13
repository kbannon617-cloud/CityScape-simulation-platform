"""Unit tests for calculate_available_labor - pure math, no database."""

import pytest

from cinis.rules.labor_rules import calculate_available_labor


def test_zero_adults_gives_zero_labor():
    assert calculate_available_labor(adult_count=0, participation_rate_percent=100) == 0


def test_full_participation_returns_full_count():
    assert calculate_available_labor(adult_count=100, participation_rate_percent=100) == 100


def test_partial_participation_rounds_down():
    # 100 * 90% = 90 exactly
    assert calculate_available_labor(adult_count=100, participation_rate_percent=90) == 90
    # 101 * 90% = 90.9 -> floors to 90
    assert calculate_available_labor(adult_count=101, participation_rate_percent=90) == 90


def test_negative_adult_count_raises():
    with pytest.raises(ValueError):
        calculate_available_labor(adult_count=-1, participation_rate_percent=100)


def test_negative_participation_rate_raises():
    with pytest.raises(ValueError):
        calculate_available_labor(adult_count=100, participation_rate_percent=-10)
