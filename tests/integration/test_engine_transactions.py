"""
Integration tests for SimulationEngine against real SQL Server.

The engine commits and rolls back on its own sessions, so these tests
commit "Test"-prefixed rows (a run, and a city for the ledger tests)
through the shared `connection`, run the engine against them, and rely on
the session-scoped cleanup in conftest.py to remove everything afterward.
Real seeded data (the CityScape city, its inventory and treasury) is never
touched.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cinis.config.settings import load_database_settings
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.services.inventory_service import InventoryService
from cinis.simulation.engine import SimulationEngine, SimulationRunNotActiveError
from cinis.simulation.tick import StepCadence, TickContext, TickStep

D = datetime.date


@pytest.fixture(scope="module")
def session_factory(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    yield sessionmaker(bind=engine)
    engine.dispose()


def _create_run(connection, start_date=D(1880, 1, 30)) -> int:
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]
    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulationEngine-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestScenarioEngine-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.SimulationRun (ScenarioID, StartSimulationDate, CurrentSimulationDate) "
        "OUTPUT INSERTED.SimulationRunID VALUES (?, ?, ?)",
        scenario_id,
        start_date,
        start_date,
    )
    run_id = cursor.fetchone()[0]
    connection.commit()
    return run_id


def _create_city(connection) -> int:
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]
    cursor.execute("INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)", f"TestWorld-{suffix}")
    world_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
        world_id,
        f"TestRegion-{suffix}",
    )
    region_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) OUTPUT INSERTED.CityID VALUES (?, ?, 0)",
        region_id,
        f"TestCity-{suffix}",
    )
    city_id = cursor.fetchone()[0]
    connection.commit()
    return city_id


def _run_state(connection, run_id):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT CurrentSimulationDate, CurrentSimulationTickID, Status "
        "FROM dbo.SimulationRun WHERE SimulationRunID = ?",
        run_id,
    )
    row = cursor.fetchone()
    connection.rollback()
    return tuple(row)


def _events(connection, run_id):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT SimulationTickID, EventType FROM dbo.SimulationEvent "
        "WHERE SimulationRunID = ? ORDER BY SimulationEventID",
        run_id,
    )
    rows = [tuple(row) for row in cursor.fetchall()]
    connection.rollback()
    return rows


def _event_step(name, event_type, cadence=StepCadence.EVERY_TICK):
    def execute(ctx: TickContext) -> None:
        SimulationRunRepository(ctx.session).add_event(
            ctx.simulation_run_id,
            ctx.simulation_tick_id,
            ctx.simulation_date,
            event_type,
        )

    return TickStep(name=name, execute=execute, cadence=cadence)


def _wheat_id(connection) -> int:
    cursor = connection.cursor()
    cursor.execute("SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
    resource_id = cursor.fetchone()[0]
    connection.rollback()
    return resource_id


def _ledger_step(name, city_id, resource_id, amount):
    def execute(ctx: TickContext) -> None:
        InventoryService(InventoryRepository(ctx.session)).record_ledger_entry(
            city_id=city_id,
            resource_id=resource_id,
            amount=amount,
            entry_date=ctx.simulation_date,
            notes="Engine integration test",
            simulation_run_id=ctx.simulation_run_id,
            simulation_tick_id=ctx.simulation_tick_id,
        )

    return TickStep(name=name, execute=execute)


def test_ticks_persist_the_run_advance_and_step_writes_and_respect_cadence(
    connection, session_factory
):
    run_id = _create_run(connection, start_date=D(1880, 1, 30))
    engine = SimulationEngine(
        session_factory,
        [
            _event_step("Daily", "DailyMarker"),
            _event_step("Monthly", "MonthlyMarker", StepCadence.MONTH_BOUNDARY),
        ],
    )

    first = engine.run_tick(run_id)  # Jan 31: ordinary day
    second = engine.run_tick(run_id)  # Feb 1: month boundary

    assert first.executed_steps == ("Daily",)
    assert second.executed_steps == ("Daily", "Monthly")
    assert _run_state(connection, run_id) == (D(1880, 2, 1), 2, "Active")
    assert _events(connection, run_id) == [
        (1, "DailyMarker"),
        (2, "DailyMarker"),
        (2, "MonthlyMarker"),
    ]


def test_a_failed_tick_rolls_back_everything_and_marks_the_run_failed(
    connection, session_factory
):
    run_id = _create_run(connection, start_date=D(1880, 1, 30))
    city_id = _create_city(connection)
    wheat_id = _wheat_id(connection)

    def fail(ctx: TickContext) -> None:
        raise RuntimeError("deliberate test failure")

    engine = SimulationEngine(
        session_factory,
        [
            _event_step("WritesEvent", "ShouldNotPersist"),
            _ledger_step("WritesLedger", city_id, wheat_id, Decimal("5")),
            TickStep(name="Fails", execute=fail),
        ],
    )

    with pytest.raises(RuntimeError, match="deliberate test failure"):
        engine.run_tick(run_id)

    # The run's date and tick did not move; only its status changed.
    assert _run_state(connection, run_id) == (D(1880, 1, 30), 0, "Failed")
    # Nothing the steps staged before the failure persisted.
    assert _events(connection, run_id) == []

    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.CityInventory WHERE CityID = ?", city_id)
    assert cursor.fetchone()[0] == 0
    cursor.execute(
        "SELECT COUNT(*) FROM dbo.InventoryLedgerEntry WHERE SimulationRunID = ?", run_id
    )
    assert cursor.fetchone()[0] == 0
    connection.rollback()

    with pytest.raises(SimulationRunNotActiveError, match="Failed"):
        engine.run_tick(run_id)


def test_traced_ledger_writes_commit_with_the_run_and_tick(connection, session_factory):
    run_id = _create_run(connection, start_date=D(1880, 1, 30))
    city_id = _create_city(connection)
    wheat_id = _wheat_id(connection)
    engine = SimulationEngine(
        session_factory, [_ledger_step("WritesLedger", city_id, wheat_id, Decimal("5"))]
    )

    engine.run_tick(run_id)

    cursor = connection.cursor()
    cursor.execute(
        "SELECT ile.SimulationRunID, ile.SimulationTickID, ile.EntryDate, ile.Amount, ci.Quantity "
        "FROM dbo.InventoryLedgerEntry ile "
        "JOIN dbo.CityInventory ci ON ci.CityInventoryID = ile.CityInventoryID "
        "WHERE ci.CityID = ?",
        city_id,
    )
    rows = cursor.fetchall()
    connection.rollback()

    assert len(rows) == 1
    run, tick, entry_date, amount, quantity = rows[0]
    assert (run, tick, entry_date) == (run_id, 1, D(1880, 1, 31))
    assert Decimal(str(amount)) == Decimal("5")
    assert Decimal(str(quantity)) == Decimal("5")


def test_a_run_that_is_not_active_is_refused_and_left_untouched(connection, session_factory):
    run_id = _create_run(connection)
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE dbo.SimulationRun SET Status = 'Completed' WHERE SimulationRunID = ?", run_id
    )
    connection.commit()

    engine = SimulationEngine(session_factory, [_event_step("Daily", "ShouldNotPersist")])
    with pytest.raises(SimulationRunNotActiveError, match="Completed"):
        engine.run_tick(run_id)

    assert _run_state(connection, run_id) == (D(1880, 1, 30), 0, "Completed")
    assert _events(connection, run_id) == []
