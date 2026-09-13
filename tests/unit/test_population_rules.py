"""Unit tests for calculate_aged_count - pure math, no database."""

import pytest

from cinis.rules.population_rules import calculate_aged_count


def test_zero_children_ages_zero():
    assert calculate_aged_count(child_count=0, rate_percent=1.5) == 0


def test_zero_rate_ages_zero():
    assert calculate_aged_count(child_count=100, rate_percent=0) == 0


def test_exact_division_ages_correctly():
    # 1000 * 1.5% = 15 exactly
    assert calculate_aged_count(child_count=1000, rate_percent=1.5) == 15


def test_fractional_result_rounds_down():
    # 20 * 1.5% = 0.3 -> floors to 0, not 1
    assert calculate_aged_count(child_count=20, rate_percent=1.5) == 0


def test_fractional_result_rounds_down_not_to_nearest():
    # 999 * 1.5% = 14.985 -> floors to 14, not rounds to 15
    assert calculate_aged_count(child_count=999, rate_percent=1.5) == 14


def test_negative_child_count_raises():
    with pytest.raises(ValueError):
        calculate_aged_count(child_count=-5, rate_percent=1.5)


def test_negative_rate_raises():
    with pytest.raises(ValueError):
        calculate_aged_count(child_count=100, rate_percent=-1.0)


def test_100_percent_rate_ages_everyone():
    assert calculate_aged_count(child_count=42, rate_percent=100) == 42
