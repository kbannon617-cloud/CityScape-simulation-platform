"""
Integration tests for ConstructionService.advance_projects (and the
Construction tick step's event logging) against real
SQL Server, using the actual seeded CityScape/Cinis Baseline data.

Stone (R-003) intentionally has ZERO opening stock (migration 0014 seeds
only Wheat and Timber) - confirmed the same way the Step 4.5b fix was:
checked against the migration file before writing assertions, not
assumed. Tests that order a building requiring Stone top it up first via
_seed_resource_stock, inside their own SAVEPOINT.

Safe by construction: neither order_project() nor advance_projects()
commits (like every other service in this codebase), so each test runs
inside one SAVEPOINT via sqlalchemy_session.begin_nested() and rolls it
back in a finally block. No SimulationEngine here and no session shared
across multiple internal commits - the Step 4.5c integration coverage is
scoped to the service, not a live multi-tick engine run against the real
primary-active city (see the Step 4.4c incident notes).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.events.event_types import CONSTRUCTION_COMPLETED
from cinis.models.construction import STATUS_COMPLETE, STATUS_IN_PROGRESS
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.repositories.construction_repository import ConstructionRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.construction_service import ConstructionService
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService
from cinis.simulation.construction_step import make_construction_step
from cinis.simulation.tick import TickContext

D = Decimal
ORDER_DATE = datetime.date(1880, 2, 1)
FIRST_TICK_DATE = datetime.date(1880, 3, 1)


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cityscape_and_baseline_ids(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT sc.ScenarioID FROM dbo.Scenario sc "
        "JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID "
        "WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'"
    )
    scenario_id = cursor.fetchone()[0]
    return city_id, scenario_id


def _build_service(session):
    return ConstructionService(
        ConstructionRepository(session),
        TreasuryService(TreasuryRepository(session)),
        InventoryService(InventoryRepository(session)),
        ProductionRepository(session),
        PopulationRepository(session),
    )


def _seed_resource_stock(sqlalchemy_session, city_id, resource_code, amount):
    """Give a resource additional opening stock within the current
    SAVEPOINT. Real seed data (migration 0014) intentionally leaves
    Stone at zero."""
    resource_id = InventoryService(InventoryRepository(sqlalchemy_session)).get_resource_id(
        resource_code
    )
    InventoryService(InventoryRepository(sqlalchemy_session)).record_ledger_entry(
        city_id=city_id,
        resource_id=resource_id,
        amount=Decimal(str(amount)),
        entry_date=datetime.date(1880, 1, 1),
        notes="Test-seeded stock.",
    )
    sqlalchemy_session.flush()


def _create_run_on_baseline(session, scenario_id):
    """A Test-prefixed Simulation/Run pointed at the REAL Cinis Baseline
    scenario - needed so order_project finds the real ScenarioParameter
    rows. Safe here only because this file never commits (step.execute
    never commits; the test's own SAVEPOINT rolls everything back) -
    unlike SimulationEngine, which does commit per tick (see the Step
    4.4c incident notes above)."""
    suffix = uuid.uuid4().hex[:8]
    simulation = Simulation(Name=f"TestSimulationConstruction-{suffix}")
    session.add(simulation)
    session.flush()
    run = SimulationRun(
        ScenarioID=scenario_id,
        StartSimulationDate=ORDER_DATE,
        CurrentSimulationDate=ORDER_DATE,
    )
    session.add(run)
    session.flush()
    return run


def _building_count(cursor, city_id, building_type_code):
    cursor.execute(
        "SELECT b.Count FROM dbo.Building b "
        "JOIN dbo.BuildingType bt ON bt.BuildingTypeID = b.BuildingTypeID "
        "WHERE b.CityID = ? AND bt.Code = ?",
        city_id,
        building_type_code,
    )
    row = cursor.fetchone()
    return row[0] if row else None


def test_a_multi_month_project_only_gets_months_elapsed_incremented(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)
        # B-002 Wheat Farm: cost 750, budget 100/month, no completed
        # crews -> AdjustedDurationMonths = 8. One tick is nowhere near done.
        project = service.order_project(city_id, scenario_id, "B-002", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        touched = service.advance_projects(city_id, FIRST_TICK_DATE)

        assert project.MonthsElapsed == 1
        assert project.Status == STATUS_IN_PROGRESS
        assert project.CompletedSimulationDate is None
        assert touched == [project]  # touched, but not completed
    finally:
        savepoint.rollback()


def test_a_one_month_project_completes_on_the_first_tick_and_creates_the_building(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)
        # B-007 Construction Crew: cost 0 -> AdjustedDurationMonths = 1
        # even with zero completed crews (the "free order still takes a
        # month" rule). CityScape has no B-007 Building row yet.
        project = service.order_project(city_id, scenario_id, "B-007", 2, ORDER_DATE)
        sqlalchemy_session.flush()
        assert project.AdjustedDurationMonths == 1

        completed = service.advance_projects(city_id, FIRST_TICK_DATE)
        sqlalchemy_session.flush()

        assert completed == [project]
        assert project.Status == STATUS_COMPLETE
        assert project.CompletedSimulationDate == FIRST_TICK_DATE

        cursor = sqlalchemy_session.connection().connection.cursor()
        assert _building_count(cursor, city_id, "B-007") == 2
    finally:
        savepoint.rollback()


def test_completing_adds_to_an_existing_real_building_count(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            "SELECT BuildingTypeID FROM dbo.BuildingType WHERE Code = 'B-007'"
        )
        crew_type_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.Building (CityID, BuildingTypeID, Count) VALUES (?, ?, ?)",
            city_id,
            crew_type_id,
            5,
        )
        sqlalchemy_session.expire_all()

        service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)
        sqlalchemy_session.flush()
        service.advance_projects(city_id, FIRST_TICK_DATE)
        sqlalchemy_session.flush()

        assert _building_count(cursor, city_id, "B-007") == 6  # 5 existing + 1 ordered
    finally:
        savepoint.rollback()


def test_two_concurrent_projects_are_each_advanced_independently(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            "UPDATE dbo.ScenarioParameter SET ParameterValue = 2 "
            "WHERE ScenarioID = ? AND ParameterKey = 'MaxActiveConstructionProjectsPerCity'",
            scenario_id,
        )
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)

        quick = service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)  # 1 month
        slow = service.order_project(city_id, scenario_id, "B-002", 1, ORDER_DATE)  # 8 months
        sqlalchemy_session.flush()

        touched = service.advance_projects(city_id, FIRST_TICK_DATE)

        assert touched == [quick, slow]  # both touched; only quick completed
        assert quick.Status == STATUS_COMPLETE
        assert slow.Status == STATUS_IN_PROGRESS and slow.MonthsElapsed == 1
    finally:
        savepoint.rollback()


def test_the_step_writes_a_construction_completed_event_on_finish(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run_on_baseline(sqlalchemy_session, scenario_id)
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)
        project = service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        context = TickContext(
            simulation_run_id=run.SimulationRunID,
            scenario_id=scenario_id,
            simulation_tick_id=1,
            simulation_date=FIRST_TICK_DATE,
            previous_date=ORDER_DATE,
            is_month_boundary=True,
            session=sqlalchemy_session,
        )
        make_construction_step().execute(context)

        events = SimulationRunRepository(sqlalchemy_session).get_events_for_tick(
            run.SimulationRunID, 1
        )
        completed_events = [e for e in events if e.EventType == CONSTRUCTION_COMPLETED]
        assert len(completed_events) == 1
        event = completed_events[0]
        assert event.CityID == city_id
        assert event.SimulationDate == FIRST_TICK_DATE
        assert '"BuildingTypeCode":"B-007"' in event.Payload
        assert f'"ConstructionProjectID":{project.ConstructionProjectID}' in event.Payload
    finally:
        savepoint.rollback()
