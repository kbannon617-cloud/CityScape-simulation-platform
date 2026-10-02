"""Unit tests for the construction tick step against fakes (no database)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from cinis.events.event_types import CONSTRUCTION_COMPLETED
from cinis.simulation.construction_step import (
    ConstructionStepDependencies,
    STEP_NAME,
    make_construction_step,
)
from cinis.simulation.tick import StepCadence, TickContext


@dataclass
class _FakeProject:
    ConstructionProjectID: int
    BuildingTypeID: int
    BuildingsOrdered: int
    Status: str = "Complete"


@dataclass
class _FakeBuildingType:
    Code: str


class _FakeConstructionService:
    def __init__(self, completed=None):
        self.calls = []
        self._completed = completed or []

    def advance_projects(self, **kwargs):
        self.calls.append(kwargs)
        return self._completed


class _FakeProductionRepository:
    def __init__(self, codes_by_id):
        self._codes_by_id = codes_by_id
        self.calls = []

    def get_building_type_by_id(self, building_type_id):
        self.calls.append(building_type_id)
        return _FakeBuildingType(Code=self._codes_by_id[building_type_id])


@dataclass
class _FakeRunRepository:
    events: list = field(default_factory=list)

    def add_event(self, **kwargs):
        self.events.append(kwargs)


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


def _run_step(completed=None, codes_by_id=None):
    service = _FakeConstructionService(completed)
    production_repo = _FakeProductionRepository(codes_by_id or {})
    run_repo = _FakeRunRepository()
    seen_sessions = []

    def factory(session):
        seen_sessions.append(session)
        return ConstructionStepDependencies(
            city_id=77,
            construction_service=service,
            production_repository=production_repo,
            run_repository=run_repo,
        )

    step = make_construction_step(factory)
    step.execute(_context())
    return step, service, production_repo, run_repo, seen_sessions


def test_step_is_named_and_runs_only_on_a_month_boundary():
    step, *_ = _run_step()
    assert step.name == STEP_NAME == "Construction"
    assert step.cadence is StepCadence.MONTH_BOUNDARY


def test_step_builds_its_dependencies_on_the_tick_session():
    *_, seen_sessions = _run_step()
    assert seen_sessions == ["the-tick-session"]


def test_step_only_advances_it_never_orders():
    """advance_projects takes no building_type_code/buildings_ordered -
    the step can only progress existing projects, never create new ones.
    See ConstructionService's docstring: ordering is a command, not a
    tick action."""
    _, service, *_ = _run_step()
    assert service.calls == [{"city_id": 77, "tick_date": datetime.date(1880, 2, 1)}]


def test_no_touched_projects_means_no_events():
    _, _, _, run_repo, _ = _run_step(completed=[])
    assert run_repo.events == []


def test_a_still_in_progress_project_logs_no_event():
    """advance_projects returns every project it touched, completed or
    not; the step must filter to Complete before logging anything."""
    touched = [
        _FakeProject(ConstructionProjectID=1, BuildingTypeID=2, BuildingsOrdered=1, Status="InProgress")
    ]
    _, _, production_repo, run_repo, _ = _run_step(completed=touched, codes_by_id={2: "B-002"})

    assert run_repo.events == []
    assert production_repo.calls == []  # never even looked up the building type


def test_a_mix_of_completed_and_in_progress_only_logs_the_completed_one():
    touched = [
        _FakeProject(ConstructionProjectID=1, BuildingTypeID=2, BuildingsOrdered=1, Status="Complete"),
        _FakeProject(ConstructionProjectID=2, BuildingTypeID=7, BuildingsOrdered=1, Status="InProgress"),
    ]
    _, _, production_repo, run_repo, _ = _run_step(touched, codes_by_id={2: "B-002"})

    assert len(run_repo.events) == 1
    assert production_repo.calls == [2]
    assert run_repo.events[0]["payload"]["ConstructionProjectID"] == 1


def test_each_completed_project_logs_one_construction_completed_event():
    completed = [
        _FakeProject(ConstructionProjectID=1, BuildingTypeID=2, BuildingsOrdered=1, Status="Complete"),
        _FakeProject(ConstructionProjectID=2, BuildingTypeID=7, BuildingsOrdered=3, Status="Complete"),
    ]
    codes = {2: "B-002", 7: "B-007"}
    _, _, production_repo, run_repo, _ = _run_step(completed=completed, codes_by_id=codes)

    assert len(run_repo.events) == 2
    assert production_repo.calls == [2, 7]

    first, second = run_repo.events
    assert first["event_type"] == CONSTRUCTION_COMPLETED == "ConstructionCompleted"
    assert first["simulation_run_id"] == 5
    assert first["simulation_tick_id"] == 32
    assert first["simulation_date"] == datetime.date(1880, 2, 1)
    assert first["city_id"] == 77
    assert first["description"] == "1x B-002 completed."
    assert first["payload"] == {
        "ConstructionProjectID": 1,
        "BuildingTypeCode": "B-002",
        "BuildingsOrdered": 1,
    }

    assert second["description"] == "3x B-007 completed."
    assert second["payload"]["BuildingsOrdered"] == 3
