"""Unit tests for the calendar rules - pure date/tick arithmetic, no database."""

import dataclasses
import datetime

import pytest

from cinis.rules.calendar_rules import TickAdvance, advance_tick, is_month_boundary

D = datetime.date


# --- is_month_boundary -------------------------------------------------


def test_mid_month_day_is_not_a_boundary():
    assert is_month_boundary(D(1880, 1, 14), D(1880, 1, 15)) is False


def test_last_day_to_first_day_of_next_month_is_a_boundary():
    assert is_month_boundary(D(1880, 1, 31), D(1880, 2, 1)) is True


def test_december_to_january_crosses_the_year_and_is_a_boundary():
    assert is_month_boundary(D(1880, 12, 31), D(1881, 1, 1)) is True


def test_same_month_in_a_different_year_is_a_boundary():
    """Year and month are both compared, not month alone."""
    assert is_month_boundary(D(1880, 1, 31), D(1881, 1, 1)) is True


def test_leap_february_has_a_29th_that_is_not_a_boundary():
    assert is_month_boundary(D(1880, 2, 28), D(1880, 2, 29)) is False
    assert is_month_boundary(D(1880, 2, 29), D(1880, 3, 1)) is True


def test_non_leap_century_year_1900_goes_from_feb_28_straight_to_march():
    assert is_month_boundary(D(1900, 2, 28), D(1900, 3, 1)) is True


@pytest.mark.parametrize(
    "previous, new",
    [(D(1880, 1, 2), D(1880, 1, 2)), (D(1880, 1, 2), D(1880, 1, 1))],
    ids=["same-date", "earlier-date"],
)
def test_new_date_must_be_after_previous_date(previous, new):
    with pytest.raises(ValueError, match="after previous_date"):
        is_month_boundary(previous, new)


# --- advance_tick ------------------------------------------------------


def test_first_tick_is_numbered_one_and_moves_the_date_one_day():
    result = advance_tick(D(1880, 1, 1), 0)
    assert result == TickAdvance(
        previous_date=D(1880, 1, 1),
        new_date=D(1880, 1, 2),
        new_tick_id=1,
        is_month_boundary=False,
    )


def test_tick_and_date_both_advance_by_exactly_one():
    result = advance_tick(D(1880, 3, 10), 68)
    assert result.new_tick_id == 69
    assert result.new_date == D(1880, 3, 11)


def test_a_run_starting_on_the_last_day_of_a_month_hits_a_boundary_on_tick_one():
    result = advance_tick(D(1880, 1, 31), 0)
    assert result.new_date == D(1880, 2, 1)
    assert result.new_tick_id == 1
    assert result.is_month_boundary is True


def test_year_end_advance_rolls_over_and_flags_a_boundary():
    result = advance_tick(D(1880, 12, 31), 365)
    assert result.new_date == D(1881, 1, 1)
    assert result.is_month_boundary is True


def test_negative_tick_id_raises():
    with pytest.raises(ValueError, match="non-negative"):
        advance_tick(D(1880, 1, 1), -1)


def test_result_is_immutable():
    result = advance_tick(D(1880, 1, 1), 0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.new_tick_id = 99


def test_advance_tick_is_deterministic():
    assert advance_tick(D(1880, 5, 5), 10) == advance_tick(D(1880, 5, 5), 10)


def test_advancing_past_the_last_supported_date_overflows():
    with pytest.raises(OverflowError):
        advance_tick(datetime.date.max, 0)


# --- whole-run behavior -------------------------------------------------


def _simulate(start: datetime.date, days: int) -> list[TickAdvance]:
    date, tick, results = start, 0, []
    for _ in range(days):
        step = advance_tick(date, tick)
        results.append(step)
        date, tick = step.new_date, step.new_tick_id
    return results


def test_a_leap_year_of_ticks_has_twelve_month_boundaries():
    """366 days from 1880-01-01 (a leap year) ends on 1881-01-01. Boundaries:
    Feb 1 through Dec 1 (eleven), plus Jan 1 1881."""
    steps = _simulate(D(1880, 1, 1), 366)
    boundary_dates = [s.new_date for s in steps if s.is_month_boundary]

    assert len(boundary_dates) == 12
    assert boundary_dates[0] == D(1880, 2, 1)
    assert boundary_dates[-1] == D(1881, 1, 1)


def test_one_hundred_ticks_from_a_first_of_the_month_has_three_boundaries():
    """Example only (start date is arbitrary, not the baseline's): 100 days
    from 1880-01-01 end on 1880-04-10, crossing Feb 1, Mar 1 and Apr 1."""
    steps = _simulate(D(1880, 1, 1), 100)

    assert steps[-1].new_tick_id == 100
    assert steps[-1].new_date == D(1880, 4, 10)
    assert [s.new_date for s in steps if s.is_month_boundary] == [
        D(1880, 2, 1),
        D(1880, 3, 1),
        D(1880, 4, 1),
    ]


def test_tick_ids_are_consecutive_with_no_gaps_or_repeats():
    steps = _simulate(D(1880, 1, 1), 50)
    assert [s.new_tick_id for s in steps] == list(range(1, 51))
