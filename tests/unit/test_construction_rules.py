"""Unit tests for construction duration rules - pure arithmetic, no database."""

from decimal import Decimal

import pytest

from cinis.rules.construction_rules import (
    compute_adjusted_duration_months,
    compute_base_duration_months,
    compute_speed_bonus,
)

D = Decimal


# --- compute_base_duration_months ---------------------------------------


def test_zero_cost_is_still_one_month():
    assert compute_base_duration_months(D("0"), D("100")) == 1


def test_exact_multiple_of_budget():
    assert compute_base_duration_months(D("300"), D("100")) == 3


def test_partial_month_rounds_up():
    assert compute_base_duration_months(D("750"), D("100")) == 8  # workbook's Wheat Farm example


def test_cost_less_than_one_months_budget_is_still_one_month():
    assert compute_base_duration_months(D("1"), D("100")) == 1


def test_negative_cost_is_treated_like_zero():
    assert compute_base_duration_months(D("-5"), D("100")) == 1


def test_zero_or_negative_budget_raises():
    with pytest.raises(ValueError, match="positive"):
        compute_base_duration_months(D("100"), D("0"))
    with pytest.raises(ValueError, match="positive"):
        compute_base_duration_months(D("100"), D("-10"))


# --- compute_speed_bonus -------------------------------------------------


def test_no_completed_crews_is_no_bonus():
    assert compute_speed_bonus(0, D("0.0005")) == D("0")


def test_bonus_scales_linearly_with_crew_count():
    assert compute_speed_bonus(4, D("0.0005")) == D("0.0020")


def test_bonus_is_uncapped_for_a_large_crew_count():
    assert compute_speed_bonus(1000, D("0.0005")) == D("0.5000")


def test_negative_crew_count_raises():
    with pytest.raises(ValueError, match="non-negative"):
        compute_speed_bonus(-1, D("0.0005"))


# --- compute_adjusted_duration_months ------------------------------------


def test_no_bonus_leaves_duration_unchanged():
    assert compute_adjusted_duration_months(8, D("0")) == 8


def test_bonus_shortens_duration():
    # 8 months / 1.002 = 7.984... -> rounds up to 8 still (workbook ROUNDUP)
    assert compute_adjusted_duration_months(8, D("0.002")) == 8


def test_large_bonus_meaningfully_shortens_duration():
    assert compute_adjusted_duration_months(8, D("0.5")) == 6  # 8 / 1.5 = 5.33 -> 6


def test_duration_never_drops_below_one_month():
    assert compute_adjusted_duration_months(1, D("100")) == 1


def test_base_duration_below_one_raises():
    with pytest.raises(ValueError, match="at least 1"):
        compute_adjusted_duration_months(0, D("0"))


def test_negative_speed_bonus_raises():
    with pytest.raises(ValueError, match="non-negative"):
        compute_adjusted_duration_months(8, D("-0.1"))
