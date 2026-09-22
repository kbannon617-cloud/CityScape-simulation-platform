"""Unit tests for the needs-consumption tick step against fakes (no database)."""

from __future__ import annotations

import datetime
from decimal import Decimal

from cinis.events.event_types import NEEDS_SHORTFALL
from cinis.services.needs_consumption_service import NeedConsumptionResult, ResourceConsumption
from cinis.simulation.needs_step import (
    STEP_NAME,
    NeedsStepDependencies,
    make_needs_consumption_step,
)
from cinis.simulation.tick import StepCadence, TickContext

D = Decimal


class _FakeConsumptionService:
    def __init__(self, results):
        self._results = results
        self.calls = []

    def consume_daily_needs(self, **kwargs):
        self.calls.append(kwargs)
        return self._results


class _FakeRunRepository:
    def __init__(self):
        self.events = []

    def add_event(self, **kwargs):
        self.events.append(kwargs)


def _context():
    return TickContext(
        simulation_run_id=5,
        scenario_id=2,
        simulation_tick_id=12,
        simulation_date=datetime.date(1880, 1, 13),
        previous_date=datetime.date(1880, 1, 12),
        is_month_boundary=False,
        session="the-tick-session",
    )


def _run_step(results):
    service = _FakeConsumptionService(results)
    repository = _FakeRunRepository()
    seen_sessions = []

    def factory(session):
        seen_sessions.append(session)
        return NeedsStepDependencies(city_id=77, consumption_service=service, run_repository=repository)

    step = make_needs_consumption_step(factory)
    step.execute(_context())
    return step, service, repository, seen_sessions


def _result(code, needed, consumed):
    return NeedConsumptionResult(
        need_type_code=code,
        needed=D(needed),
        consumed=D(consumed),
        consumption_by_resource=(ResourceConsumption("R-001", D(consumed)),),
    )


def test_step_is_named_and_runs_every_tick():
    step, *_ = _run_step([])
    assert step.name == STEP_NAME == "NeedsConsumption"
    assert step.cadence is StepCadence.EVERY_TICK


def test_step_builds_its_dependencies_on_the_tick_session():
    _, _, _, seen_sessions = _run_step([])
    assert seen_sessions == ["the-tick-session"]


def test_step_passes_city_date_and_trace_to_the_consumption_service():
    _, service, _, _ = _run_step([])

    assert service.calls == [
        {
            "city_id": 77,
            "entry_date": datetime.date(1880, 1, 13),
            "simulation_run_id": 5,
            "simulation_tick_id": 12,
        }
    ]


def test_no_event_is_written_when_every_need_is_met():
    _, _, repository, _ = _run_step([_result("FOOD", "110", "110"), _result("HEATING", "88", "88")])
    assert repository.events == []


def test_a_shortfall_writes_one_event_with_exact_decimal_payload():
    _, _, repository, _ = _run_step([_result("FOOD", "110.0000", "100.0000"), _result("HEATING", "88", "88")])

    (event,) = repository.events
    assert event == {
        "simulation_run_id": 5,
        "simulation_tick_id": 12,
        "simulation_date": datetime.date(1880, 1, 13),
        "event_type": NEEDS_SHORTFALL,
        "city_id": 77,
        "description": "FOOD need not fully met.",
        "payload": {
            "NeedTypeCode": "FOOD",
            "Needed": D("110.0000"),
            "Consumed": D("100.0000"),
            "Shortfall": D("10.0000"),
        },
    }


def test_each_short_need_gets_its_own_event_in_result_order():
    _, _, repository, _ = _run_step([_result("FOOD", "10", "0"), _result("HEATING", "8", "1")])

    assert [e["payload"]["NeedTypeCode"] for e in repository.events] == ["FOOD", "HEATING"]


def test_no_results_at_all_writes_no_events():
    _, _, repository, _ = _run_step([])
    assert repository.events == []


def test_event_type_constant_value():
    assert NEEDS_SHORTFALL == "NeedsShortfall"
