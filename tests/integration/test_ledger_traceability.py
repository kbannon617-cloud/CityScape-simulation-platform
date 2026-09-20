"""
Integration tests for the 0020 run/tick columns on TreasuryLedgerEntry and
InventoryLedgerEntry (ADR-0009 Decision 3), run against real SQL Server.

Nothing here persists: ORM tests work inside a SAVEPOINT that is rolled
back, and constraint tests use an uncommitted raw transaction that is
rolled back in a finally block.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.models.economy import TreasuryLedgerEntry
from cinis.models.inventory import InventoryLedgerEntry
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService

ENTRY_DATE = datetime.date(1880, 1, 2)

# Raw INSERT for one ledger row of each table, parameterized on
# (run_id, tick_id). Uses real seeded parent rows so only the trace
# columns can cause a rejection.
RAW_INSERTS = {
    "InventoryLedgerEntry": (
        "INSERT INTO dbo.InventoryLedgerEntry "
        "(CityInventoryID, EntryDate, Amount, SimulationRunID, SimulationTickID) "
        "SELECT TOP 1 CityInventoryID, '1880-01-02', 1, ?, ? FROM dbo.CityInventory"
    ),
    "TreasuryLedgerEntry": (
        "INSERT INTO dbo.TreasuryLedgerEntry "
        "(TreasuryID, TreasuryCategoryTypeID, EntryDate, Amount, SimulationRunID, SimulationTickID) "
        "SELECT TOP 1 t.TreasuryID, "
        "(SELECT TOP 1 TreasuryCategoryTypeID FROM dbo.TreasuryCategoryType), "
        "'1880-01-02', 1, ?, ? FROM dbo.Treasury t"
    ),
}


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


def _create_run(session: Session) -> SimulationRun:
    suffix = uuid.uuid4().hex[:8]
    simulation = Simulation(Name=f"TestSimulationLedgerTrace-{suffix}")
    session.add(simulation)
    session.flush()
    scenario = Scenario(
        SimulationID=simulation.SimulationID, Name=f"TestScenarioLedgerTrace-{suffix}"
    )
    session.add(scenario)
    session.flush()
    run = SimulationRun(
        ScenarioID=scenario.ScenarioID,
        StartSimulationDate=ENTRY_DATE,
        CurrentSimulationDate=ENTRY_DATE,
    )
    session.add(run)
    session.flush()
    return run


def _insert_run_raw(cursor) -> int:
    suffix = uuid.uuid4().hex[:8]
    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulationLedgerTraceRaw-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestScenarioLedgerTraceRaw-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.SimulationRun (ScenarioID, StartSimulationDate, CurrentSimulationDate) "
        "OUTPUT INSERTED.SimulationRunID VALUES (?, '1880-01-01', '1880-01-01')",
        scenario_id,
    )
    return cursor.fetchone()[0]


@pytest.mark.parametrize("table", ["InventoryLedgerEntry", "TreasuryLedgerEntry"])
def test_columns_foreign_key_and_checks_exist(connection, table):
    cursor = connection.cursor()

    cursor.execute(
        "SELECT c.name, c.is_nullable, t.name FROM sys.columns c "
        "JOIN sys.types t ON t.user_type_id = c.user_type_id "
        "WHERE c.object_id = OBJECT_ID(?) AND c.name IN ('SimulationRunID', 'SimulationTickID')",
        f"dbo.{table}",
    )
    columns = {name: (bool(nullable), type_name) for name, nullable, type_name in cursor.fetchall()}
    assert columns == {
        "SimulationRunID": (True, "int"),
        "SimulationTickID": (True, "bigint"),
    }

    cursor.execute(
        "SELECT name FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(?)", f"dbo.{table}"
    )
    assert f"FK_{table}_SimulationRun" in {row[0] for row in cursor.fetchall()}

    cursor.execute(
        "SELECT name FROM sys.check_constraints WHERE parent_object_id = OBJECT_ID(?)",
        f"dbo.{table}",
    )
    names = {row[0] for row in cursor.fetchall()}
    assert f"CK_{table}_Trace_BothOrNeither" in names
    assert f"CK_{table}_SimulationTickID_Positive" in names


@pytest.mark.parametrize("table", ["InventoryLedgerEntry", "TreasuryLedgerEntry"])
@pytest.mark.parametrize("trace", [(1, None), (None, 1)], ids=["run-only", "tick-only"])
def test_database_rejects_a_partial_trace(connection, table, trace):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        run = run_id if trace[0] is not None else None
        with pytest.raises(pyodbc.Error):
            cursor.execute(RAW_INSERTS[table], run, trace[1])
    finally:
        connection.rollback()


@pytest.mark.parametrize("table", ["InventoryLedgerEntry", "TreasuryLedgerEntry"])
def test_database_rejects_tick_zero(connection, table):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        with pytest.raises(pyodbc.Error):
            cursor.execute(RAW_INSERTS[table], run_id, 0)
    finally:
        connection.rollback()


@pytest.mark.parametrize("table", ["InventoryLedgerEntry", "TreasuryLedgerEntry"])
def test_database_rejects_a_nonexistent_run(connection, table):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            cursor.execute(RAW_INSERTS[table], -1, 1)
    finally:
        connection.rollback()


@pytest.mark.parametrize("table", ["InventoryLedgerEntry", "TreasuryLedgerEntry"])
def test_database_accepts_a_full_trace_and_no_trace(connection, table):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        cursor.execute(RAW_INSERTS[table], run_id, 1)
        cursor.execute(RAW_INSERTS[table], None, None)
    finally:
        connection.rollback()


def test_inventory_service_records_trace_and_defaults_to_null(sqlalchemy_session, cityscape_id):
    service = InventoryService(InventoryRepository(sqlalchemy_session))

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute("SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
        wheat_id = cursor.fetchone()[0]

        service.record_ledger_entry(
            city_id=cityscape_id,
            resource_id=wheat_id,
            amount=Decimal("-1"),
            entry_date=ENTRY_DATE,
            notes="Traced consumption.",
            simulation_run_id=run.SimulationRunID,
            simulation_tick_id=1,
        )
        service.record_ledger_entry(
            city_id=cityscape_id,
            resource_id=wheat_id,
            amount=Decimal("1"),
            entry_date=ENTRY_DATE,
            notes="Untraced entry.",
        )
        sqlalchemy_session.flush()

        traced = (
            sqlalchemy_session.query(InventoryLedgerEntry)
            .filter(InventoryLedgerEntry.SimulationRunID == run.SimulationRunID)
            .one()
        )
        assert traced.SimulationTickID == 1
        assert traced.Notes == "Traced consumption."

        untraced = (
            sqlalchemy_session.query(InventoryLedgerEntry)
            .filter(InventoryLedgerEntry.Notes == "Untraced entry.")
            .one()
        )
        assert untraced.SimulationRunID is None
        assert untraced.SimulationTickID is None
    finally:
        savepoint.rollback()


def test_treasury_service_records_trace_and_defaults_to_null(sqlalchemy_session, cityscape_id):
    service = TreasuryService(TreasuryRepository(sqlalchemy_session))

    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)

        service.record_ledger_entry(
            city_id=cityscape_id,
            category_code="RESIDENT_INCOME",
            amount=Decimal("11.1100"),
            entry_date=ENTRY_DATE,
            simulation_run_id=run.SimulationRunID,
            simulation_tick_id=2,
        )
        service.record_ledger_entry(
            city_id=cityscape_id,
            category_code="RESIDENT_INCOME",
            amount=Decimal("22.2200"),
            entry_date=ENTRY_DATE,
        )
        sqlalchemy_session.flush()

        traced = (
            sqlalchemy_session.query(TreasuryLedgerEntry)
            .filter(TreasuryLedgerEntry.SimulationRunID == run.SimulationRunID)
            .one()
        )
        assert traced.SimulationTickID == 2
        assert traced.Amount == Decimal("11.1100")

        untraced = (
            sqlalchemy_session.query(TreasuryLedgerEntry)
            .filter(TreasuryLedgerEntry.Amount == Decimal("22.2200"))
            .filter(TreasuryLedgerEntry.EntryDate == ENTRY_DATE)
            .one()
        )
        assert untraced.SimulationRunID is None
        assert untraced.SimulationTickID is None
    finally:
        savepoint.rollback()


def test_partial_trace_is_rejected_by_the_service_before_any_write(
    sqlalchemy_session, cityscape_id
):
    service = TreasuryService(TreasuryRepository(sqlalchemy_session))

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = service.get_balance(cityscape_id)
        with pytest.raises(ValueError, match="together"):
            service.record_ledger_entry(
                city_id=cityscape_id,
                category_code="RESIDENT_INCOME",
                amount=Decimal("5"),
                entry_date=ENTRY_DATE,
                simulation_tick_id=1,
            )
        assert service.get_balance(cityscape_id) == starting_balance
    finally:
        savepoint.rollback()
