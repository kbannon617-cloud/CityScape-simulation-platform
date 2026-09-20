"""
Calendar rules: pure date and tick arithmetic, no database access.

ADR-0009 Decision 1: one tick is one simulated day. Steps that run only
once a month (population aging, labor and production) fire on a
"month-boundary tick" - a tick whose date falls in a different calendar
month (year and month) than the run's date before that tick was advanced.

Time progresses only through the run's SimulationTickID and SimulationDate
(Master Prompt Section 7); nothing here reads the wall clock.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class TickAdvance:
    """The result of advancing a run by one tick."""

    previous_date: datetime.date
    new_date: datetime.date
    new_tick_id: int
    is_month_boundary: bool


def is_month_boundary(previous_date: datetime.date, new_date: datetime.date) -> bool:
    """Return True if new_date is in a different calendar month (year and
    month) than previous_date.

    new_date must be later than previous_date; a run's date only moves
    forward. Raises ValueError otherwise.
    """
    if new_date <= previous_date:
        raise ValueError(
            f"new_date must be after previous_date, got previous_date={previous_date}, "
            f"new_date={new_date}"
        )
    return (new_date.year, new_date.month) != (previous_date.year, previous_date.month)


def advance_tick(current_date: datetime.date, current_tick_id: int) -> TickAdvance:
    """Advance a run by one tick (one simulated day).

    current_tick_id is the run's CurrentSimulationTickID: 0 means no tick has
    executed yet, so the first tick is numbered 1. Raises ValueError if it is
    negative. Raises OverflowError (from datetime) past the last supported
    date.
    """
    if current_tick_id < 0:
        raise ValueError(f"current_tick_id must be non-negative, got {current_tick_id}")

    new_date = current_date + datetime.timedelta(days=1)
    return TickAdvance(
        previous_date=current_date,
        new_date=new_date,
        new_tick_id=current_tick_id + 1,
        is_month_boundary=is_month_boundary(current_date, new_date),
    )
