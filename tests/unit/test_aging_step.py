"""Unit tests for the population-aging tick step against fakes (no database)."""

from __future__ import annotations

import datetime

from cinis.simulation.aging_step import AgingStepDependencies, STEP_NAME, make_aging_step
from cinis.simulation.tick import StepCadence, TickContext


class _FakePopulationService:
    def __init__(self):
        self.calls = []

    def apply_monthly_aging(self, city_id, scenario_id):
        self.calls.append((city_id, scenario_id))


def _context(scenario_id=2, is_month_boundary=True):
    return TickContext(
        simulation_run_id=5,
        scenario_id=scenario_id,
        simulation_tick_id=32,
        simulation_date=datetime.date(1880, 2, 1),
        previous_date=datetime.date(1880, 1, 31),
        is_month_boundary=is_month_boundary,
        session="the-tick-session",
    )


def _run_step(scenario_id=2):
    service = _FakePopulationService()
    seen_sessions = []

    def factory(session):
        seen_sessions.append(session)
        return AgingStepDependencies(city_id=77, population_service=service)

    step = make_aging_step(factory)
    step.execute(_context(scenario_id=scenario_id))
    return step, service, seen_sessions


def test_step_is_named_and_runs_only_on_a_month_boundary():
    step, *_ = _run_step()
    assert step.name == STEP_NAME == "PopulationAging"
    assert step.cadence is StepCadence.MONTH_BOUNDARY


def test_step_builds_its_dependencies_on_the_tick_session():
    _, _, seen_sessions = _run_step()
    assert seen_sessions == ["the-tick-session"]


def test_step_ages_the_dependency_supplied_city_with_the_context_scenario():
    _, service, _ = _run_step(scenario_id=9)
    assert service.calls == [(77, 9)]
