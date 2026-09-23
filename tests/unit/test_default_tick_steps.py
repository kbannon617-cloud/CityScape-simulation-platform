"""Unit tests for the assembled M4 step list (simulation/steps.py)."""

from cinis.simulation.aging_step import STEP_NAME as AGING_STEP_NAME
from cinis.simulation.needs_step import STEP_NAME as NEEDS_STEP_NAME
from cinis.simulation.production_step import STEP_NAME as PRODUCTION_STEP_NAME
from cinis.simulation.steps import build_default_tick_steps
from cinis.simulation.tick import StepCadence


def test_steps_are_ordered_aging_then_production_then_needs():
    steps = build_default_tick_steps()
    assert [step.name for step in steps] == [
        AGING_STEP_NAME,
        PRODUCTION_STEP_NAME,
        NEEDS_STEP_NAME,
    ]


def test_month_boundary_steps_precede_the_every_tick_step():
    steps = build_default_tick_steps()
    assert [step.cadence for step in steps] == [
        StepCadence.MONTH_BOUNDARY,
        StepCadence.MONTH_BOUNDARY,
        StepCadence.EVERY_TICK,
    ]


def test_step_names_are_unique_so_the_engine_accepts_the_list():
    from cinis.simulation.engine import SimulationEngine

    # Raises ValueError on duplicate names; a fake session factory is
    # enough since the engine is never actually run here.
    SimulationEngine(lambda: None, build_default_tick_steps())


def test_each_call_returns_independent_step_instances():
    first, second = build_default_tick_steps(), build_default_tick_steps()
    assert first is not second
    assert all(a is not b for a, b in zip(first, second))
