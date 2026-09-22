"""
Integration tests for needs consumption (ADR-0010) against real SQL Server:
the mapping repository, NeedsConsumptionService, and the needs-consumption
tick step, all working on the real CityScape city.

Every test that changes stock works inside a SAVEPOINT that is rolled back,
so real seeded inventory is never changed. Stock levels are set explicitly
inside each test (through InventoryService, the single write path) and
expectations are computed from the live need totals, so the tests do not
depend on the placeholder rates or opening stock, which will change when
balancing starts. They do depend on the seeded need-to-resource mapping
from ADR-0010 (FOOD: Wheat, Trout, Eggs, Lentils; HEATING: Timber).

The step is executed directly on the savepoint's session, not through
SimulationEngine, because the engine commits and that would permanently
deplete the real city's stock. Engine behavior is covered separately in
tests/integration/test_engine_transactions.py.
"""

from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.events.event_types import NEEDS_SHORTFALL
from cinis.models.inventory import InventoryLedgerEntry
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.need_resource_repository import NeedResourceRepository
from cinis.repositories.needs_repository import NeedsRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.rules.quantity_rules import floor_to_ledger_precision
from cinis.services.inventory_service import InventoryService
from cinis.services.needs_consumption_service import NeedsConsumptionService
from cinis.services.needs_service import NeedsService
from cinis.simulation.needs_step import make_needs_consumption_step
from cinis.simulation.tick import TickContext

D = Decimal
SETUP_DATE = datetime.date(1880, 1, 1)
TICK_DATE = datetime.date(1880, 1, 31)

FOOD_ORDER = ["R-001", "R-002", "R-009", "R-010"]  # Wheat, Trout, Eggs, Lentils
TIMBER = "R-004"


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cityscape_id(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    return cursor.fetchone()[0]


@pytest.fixture
def resource_ids(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT Code, ResourceID FROM dbo.Resource")
    return {code: resource_id for code, resource_id in cursor.fetchall()}


def _create_run(session: Session) -> SimulationRun:
    suffix = uuid.uuid4().hex[:8]
    simulation = Simulation(Name=f"TestSimulationNeeds-{suffix}")
    session.add(simulation)
    session.flush()
    scenario = Scenario(SimulationID=simulation.SimulationID, Name=f"TestScenarioNeeds-{suffix}")
    session.add(scenario)
    session.flush()
    run = SimulationRun(
        ScenarioID=scenario.ScenarioID,
        StartSimulationDate=SETUP_DATE,
        CurrentSimulationDate=SETUP_DATE,
    )
    session.add(run)
    session.flush()
    return run


def _build_service(session: Session) -> tuple[NeedsConsumptionService, NeedsService, InventoryService]:
    needs_service = NeedsService(NeedsRepository(session), PopulationRepository(session))
    inventory_service = InventoryService(InventoryRepository(session))
    service = NeedsConsumptionService(
        needs_service, NeedResourceRepository(session), inventory_service
    )
    return service, needs_service, inventory_service


def _set_stock(inventory_service, city_id, resource_ids, code, target: Decimal) -> None:
    """Set a resource's stock to an exact level through the single write
    path (a signed ledger entry for the difference)."""
    delta = target - inventory_service.get_quantity(city_id, code)
    if delta != 0:
        inventory_service.record_ledger_entry(
            city_id=city_id,
            resource_id=resource_ids[code],
            amount=delta,
            entry_date=SETUP_DATE,
            notes="Test setup.",
        )


def _daily_totals(needs_service, city_id) -> dict[str, Decimal]:
    totals = {
        t.need_type_code: floor_to_ledger_precision(t.total_quantity)
        for t in needs_service.calculate_daily_need_totals_exact(city_id)
    }
    assert totals["FOOD"] > 0 and totals["HEATING"] > 0, "test needs a non-zero population"
    return totals


def test_mapping_repository_returns_seeded_resources_in_priority_order(sqlalchemy_session):
    mapping = NeedResourceRepository(sqlalchemy_session).get_resources_by_need_type()

    assert [m.resource_code for m in mapping["FOOD"]][:4] == FOOD_ORDER
    assert [m.resource_code for m in mapping["HEATING"]][:1] == [TIMBER]
    assert all(m.resource_id > 0 for resources in mapping.values() for m in resources)


def test_food_is_drained_in_priority_order_and_heating_from_timber(
    sqlalchemy_session, cityscape_id, resource_ids
):
    service, needs_service, inventory = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        totals = _daily_totals(needs_service, cityscape_id)
        food, heating = totals["FOOD"], totals["HEATING"]

        wheat = floor_to_ledger_precision(food * D("0.5"))
        trout = floor_to_ledger_precision(food * D("0.3"))
        eggs = floor_to_ledger_precision(food * D("0.1"))
        for code, target in zip(FOOD_ORDER, [wheat, trout, eggs, food]):
            _set_stock(inventory, cityscape_id, resource_ids, code, target)
        _set_stock(inventory, cityscape_id, resource_ids, TIMBER, heating * 2)

        results = {
            r.need_type_code: r
            for r in service.consume_daily_needs(cityscape_id, TICK_DATE, run.SimulationRunID, 1)
        }

        food_result = results["FOOD"]
        lentils_used = food - (wheat + trout + eggs)
        assert [(c.resource_code, c.quantity) for c in food_result.consumption_by_resource] == [
            ("R-001", wheat),
            ("R-002", trout),
            ("R-009", eggs),
            ("R-010", lentils_used),
        ]
        assert food_result.needed == food
        assert food_result.consumed == food
        assert food_result.shortfall == 0

        assert results["HEATING"].consumed == heating
        assert inventory.get_quantity(cityscape_id, TIMBER) == heating
        assert inventory.get_quantity(cityscape_id, "R-001") == 0
        assert inventory.get_quantity(cityscape_id, "R-010") == food - lentils_used

        entries = (
            sqlalchemy_session.query(InventoryLedgerEntry)
            .filter(InventoryLedgerEntry.SimulationRunID == run.SimulationRunID)
            .all()
        )
        assert len(entries) == 5  # four FOOD resources + Timber
        assert all(e.SimulationTickID == 1 and e.EntryDate == TICK_DATE for e in entries)
        assert all(e.Amount < 0 for e in entries)
        assert sum(-e.Amount for e in entries) == food + heating
    finally:
        savepoint.rollback()


def test_a_shortfall_consumes_all_available_stock_and_reports_the_rest(
    sqlalchemy_session, cityscape_id, resource_ids
):
    service, needs_service, inventory = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        totals = _daily_totals(needs_service, cityscape_id)
        food = totals["FOOD"]
        assert food > 1, "test needs a food need above 1"

        _set_stock(inventory, cityscape_id, resource_ids, "R-001", D("1"))
        for code in FOOD_ORDER[1:]:
            _set_stock(inventory, cityscape_id, resource_ids, code, D("0"))
        _set_stock(inventory, cityscape_id, resource_ids, TIMBER, totals["HEATING"] * 2)

        results = {r.need_type_code: r for r in service.consume_daily_needs(cityscape_id, TICK_DATE)}

        assert results["FOOD"].consumed == D("1")
        assert results["FOOD"].shortfall == food - 1
        assert [c.resource_code for c in results["FOOD"].consumption_by_resource] == ["R-001"]
        assert inventory.get_quantity(cityscape_id, "R-001") == 0
        assert results["HEATING"].shortfall == 0
    finally:
        savepoint.rollback()


def test_the_step_writes_traced_consumption_and_a_shortfall_event(
    sqlalchemy_session, cityscape_id, resource_ids
):
    _, needs_service, inventory = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        totals = _daily_totals(needs_service, cityscape_id)
        food = totals["FOOD"]
        assert food > 1, "test needs a food need above 1"

        _set_stock(inventory, cityscape_id, resource_ids, "R-001", D("1"))
        for code in FOOD_ORDER[1:]:
            _set_stock(inventory, cityscape_id, resource_ids, code, D("0"))
        _set_stock(inventory, cityscape_id, resource_ids, TIMBER, totals["HEATING"] * 2)

        context = TickContext(
            simulation_run_id=run.SimulationRunID,
            scenario_id=run.ScenarioID,
            simulation_tick_id=1,
            simulation_date=TICK_DATE,
            previous_date=TICK_DATE - datetime.timedelta(days=1),
            is_month_boundary=False,
            session=sqlalchemy_session,
        )
        make_needs_consumption_step().execute(context)

        events = SimulationRunRepository(sqlalchemy_session).get_events_for_tick(
            run.SimulationRunID, 1
        )
        shortfalls = {
            json.loads(e.Payload)["NeedTypeCode"]: (e, json.loads(e.Payload))
            for e in events
            if e.EventType == NEEDS_SHORTFALL
        }
        assert "HEATING" not in shortfalls  # Timber was sufficient
        event, payload = shortfalls["FOOD"]
        assert event.CityID == cityscape_id
        assert event.SimulationDate == TICK_DATE
        assert D(payload["Needed"]) == food
        assert D(payload["Consumed"]) == D("1")
        assert D(payload["Shortfall"]) == food - 1

        traced = (
            sqlalchemy_session.query(InventoryLedgerEntry)
            .filter(InventoryLedgerEntry.SimulationRunID == run.SimulationRunID)
            .all()
        )
        assert len(traced) == 2  # Wheat (all 1 of it) and Timber
        assert all(e.SimulationTickID == 1 and e.EntryDate == TICK_DATE for e in traced)
    finally:
        savepoint.rollback()


def test_the_step_writes_no_event_when_every_mapped_need_is_met(
    sqlalchemy_session, cityscape_id, resource_ids
):
    _, needs_service, inventory = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        totals = _daily_totals(needs_service, cityscape_id)
        _set_stock(inventory, cityscape_id, resource_ids, "R-001", totals["FOOD"] * 2)
        _set_stock(inventory, cityscape_id, resource_ids, TIMBER, totals["HEATING"] * 2)

        context = TickContext(
            simulation_run_id=run.SimulationRunID,
            scenario_id=run.ScenarioID,
            simulation_tick_id=1,
            simulation_date=TICK_DATE,
            previous_date=TICK_DATE - datetime.timedelta(days=1),
            is_month_boundary=False,
            session=sqlalchemy_session,
        )
        make_needs_consumption_step().execute(context)

        events = SimulationRunRepository(sqlalchemy_session).get_events_for_tick(
            run.SimulationRunID, 1
        )
        assert [e for e in events if e.EventType == NEEDS_SHORTFALL] == []
    finally:
        savepoint.rollback()
