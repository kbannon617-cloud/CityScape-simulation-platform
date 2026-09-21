"""Unit tests for the tick building blocks - no database."""

import dataclasses
import datetime

import pytest

from cinis.simulation.tick import StepCadence, TickContext, TickResult, TickStep


def _context(is_month_boundary):
    return TickContext(
        simulation_run_id=1,
        scenario_id=1,
        simulation_tick_id=1,
        simulation_date=datetime.date(1880, 1, 2),
        previous_date=datetime.date(1880, 1, 1),
        is_month_boundary=is_month_boundary,
        session=None,
    )


def _noop(ctx):
    return None


def test_every_tick_step_applies_on_any_day():
    step = TickStep(name="Daily", execute=_noop)
    assert step.cadence is StepCadence.EVERY_TICK
    assert step.applies_to(_context(False))
    assert step.applies_to(_context(True))


def test_month_boundary_step_applies_only_on_a_boundary():
    step = TickStep(name="Monthly", execute=_noop, cadence=StepCadence.MONTH_BOUNDARY)
    assert not step.applies_to(_context(False))
    assert step.applies_to(_context(True))


def test_tick_types_are_immutable():
    step = TickStep(name="Daily", execute=_noop)
    with pytest.raises(dataclasses.FrozenInstanceError):
        step.name = "Other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        _context(False).simulation_tick_id = 5
    result = TickResult(1, 1, datetime.date(1880, 1, 2), False, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.simulation_tick_id = 5
