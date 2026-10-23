"""Unit tests for the snapshot tick step against fakes (no database)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from cinis.simulation.snapshot_step import SnapshotStepDependencies, STEP_NAME, make_snapshot_step
from cinis.simulation.tick import StepCadence, TickContext


@dataclass
class _FakeGroup:
    Count: int


class _FakePopulationRepository:
    def __init__(self, adult=100, child=20):
        self._counts = {"ADULT": adult, "CHILD": child}

    def get_group(self, city_id, code):
        return _FakeGroup(Count=self._counts[code])


class _FakeTreasuryService:
    def __init__(self, balance=Decimal("500.00")):
        self._balance = balance

    def get_balance(self, city_id):
        return self._balance


class _FakeInventoryService:
    def __init__(self, quantities=None):
        self._quantities = quantities or {}

    def get_quantity(self, city_id, code):
        return self._quantities.get(code, Decimal("0"))


class _FakeProductionRepository:
    def get_city_buildings(self, city_id):
        return {"B-002": 1}


class _FakeVehicleRepository:
    def get_city_vehicles(self, city_id):
        return {"V-001": 2}


@dataclass
class _FakeSnapshotRepository:
    calls: list = field(default_factory=list)

    def record_snapshot(self, **kwargs):
        self.calls.append(kwargs)


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


def _run_step(adult=100, child=20, balance=Decimal("500.00"), quantities=None):
    snapshot_repo = _FakeSnapshotRepository()
    seen_sessions = []

    def factory(session):
        seen_sessions.append(session)
        return SnapshotStepDependencies(
            city_id=77,
            population_repository=_FakePopulationRepository(adult, child),
            treasury_service=_FakeTreasuryService(balance),
            inventory_service=_FakeInventoryService(quantities),
            production_repository=_FakeProductionRepository(),
            vehicle_repository=_FakeVehicleRepository(),
            snapshot_repository=snapshot_repo,
        )

    step = make_snapshot_step(factory)
    step.execute(_context())
    return step, snapshot_repo, seen_sessions


def test_step_is_named_and_runs_only_on_a_month_boundary():
    step, *_ = _run_step()
    assert step.name == STEP_NAME == "Snapshot"
    assert step.cadence is StepCadence.MONTH_BOUNDARY


def test_step_builds_its_dependencies_on_the_tick_session():
    *_, seen_sessions = _run_step()
    assert seen_sessions == ["the-tick-session"]


def test_snapshot_carries_the_tick_context_identifiers():
    _, repo, _ = _run_step()
    (call,) = repo.calls
    assert call["simulation_run_id"] == 5
    assert call["simulation_tick_id"] == 32
    assert call["simulation_date"] == datetime.date(1880, 2, 1)
    assert call["city_id"] == 77


def test_payload_includes_population_treasury_inventory_buildings_and_vehicles():
    _, repo, _ = _run_step(
        adult=100, child=20, balance=Decimal("500.00"),
        quantities={"R-001": Decimal("75.0000"), "R-004": Decimal("50.0000")},
    )
    payload = repo.calls[0]["payload"]

    assert payload["AdultCount"] == 100
    assert payload["ChildCount"] == 20
    assert payload["TreasuryBalance"] == "500.00"
    assert payload["Inventory"]["R-001"] == "75.0000"
    assert payload["Inventory"]["R-004"] == "50.0000"
    assert payload["Buildings"] == {"B-002": 1}
    assert payload["Vehicles"] == {"V-001": 2}


def test_untracked_resources_default_to_zero_in_the_payload():
    _, repo, _ = _run_step(quantities={})
    payload = repo.calls[0]["payload"]
    assert all(payload["Inventory"][code] == "0" for code in payload["Inventory"])
