"""Unit tests for the production tick step against fakes (no database)."""

from __future__ import annotations

import datetime

from cinis.simulation.production_step import (
    ProductionStepDependencies,
    STEP_NAME,
    make_production_step,
)
from cinis.simulation.tick import StepCadence, TickContext


class _FakeProductionService:
    def __init__(self):
        self.calls = []

    def execute_monthly_production(self, **kwargs):
        self.calls.append(kwargs)
        return []


def _context():
    return TickContext(
        simulation_run_id=5,
        scenario_id=9,
        simulation_tick_id=32,
        simulation_date=datetime.date(1880, 2, 1),
        previous_date=datetime.date(1880, 1, 31),
        is_month_boundary=True,
        session="the-tick-session",
    )


def _run_step():
    service = _FakeProductionService()
    seen_sessions = []

    def factory(session):
        seen_sessions.append(session)
        return ProductionStepDependencies(city_id=77, production_service=service)

    step = make_production_step(factory)
    step.execute(_context())
    return step, service, seen_sessions


def test_step_is_named_and_runs_only_on_a_month_boundary():
    step, *_ = _run_step()
    assert step.name == STEP_NAME == "Production"
    assert step.cadence is StepCadence.MONTH_BOUNDARY


def test_step_builds_its_dependencies_on_the_tick_session():
    _, _, seen_sessions = _run_step()
    assert seen_sessions == ["the-tick-session"]


def test_step_passes_city_scenario_date_and_trace_through():
    _, service, _ = _run_step()
    assert service.calls == [
        {
            "city_id": 77,
            "scenario_id": 9,
            "entry_date": datetime.date(1880, 2, 1),
            "simulation_run_id": 5,
            "simulation_tick_id": 32,
        }
    ]
