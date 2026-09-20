"""
Integration tests for the SimulationEvent table (migration 0019) and
SimulationRunRepository, run against real SQL Server.

Nothing here persists: ORM-based tests work inside a SAVEPOINT that is
rolled back, and constraint tests use an uncommitted raw transaction that
is rolled back in a finally block.
"""

from __future__ import annotations

import datetime
import uuid

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.repositories.simulation_run_repository import (
    SimulationRunNotFoundError,
    SimulationRunRepository,
)

RUN_DATE = datetime.date(1880, 1, 1)


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
    simulation = Simulation(Name=f"TestSimulationEvents-{suffix}")
    session.add(simulation)
    session.flush()
    scenario = Scenario(SimulationID=simulation.SimulationID, Name=f"TestScenarioEvents-{suffix}")
    session.add(scenario)
    session.flush()
    run = SimulationRun(
        ScenarioID=scenario.ScenarioID,
        StartSimulationDate=RUN_DATE,
        CurrentSimulationDate=RUN_DATE,
    )
    session.add(run)
    session.flush()
    return run


def test_simulation_event_table_and_constraints_exist(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'SimulationEvent'")
    assert cursor.fetchone()[0] == 1

    cursor.execute(
        "SELECT name FROM sys.check_constraints "
        "WHERE parent_object_id = OBJECT_ID('dbo.SimulationEvent')"
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {
        "CK_SimulationEvent_SimulationTickID_Positive",
        "CK_SimulationEvent_Payload_IsJson",
    }


def test_get_run_returns_run_and_raises_for_missing(sqlalchemy_session):
    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        repo = SimulationRunRepository(sqlalchemy_session)

        assert repo.get_run(run.SimulationRunID) is run
        assert run.CurrentSimulationTickID == 0
        assert run.Status == "Active"

        with pytest.raises(SimulationRunNotFoundError):
            repo.get_run(-1)
    finally:
        savepoint.rollback()


def test_events_round_trip_in_insertion_order_filtered_by_tick(sqlalchemy_session, cityscape_id):
    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        repo = SimulationRunRepository(sqlalchemy_session)
        day1 = RUN_DATE + datetime.timedelta(days=1)

        repo.add_event(run.SimulationRunID, 1, day1, "First", city_id=cityscape_id,
                       payload={"b": 1, "a": 2})
        repo.add_event(run.SimulationRunID, 1, day1, "Second")
        repo.add_event(run.SimulationRunID, 2, RUN_DATE + datetime.timedelta(days=2), "NextTick")

        tick1 = repo.get_events_for_tick(run.SimulationRunID, 1)
        tick2 = repo.get_events_for_tick(run.SimulationRunID, 2)

        assert [e.EventType for e in tick1] == ["First", "Second"]
        assert [e.EventType for e in tick2] == ["NextTick"]
        assert tick1[0].CityID == cityscape_id
        assert tick1[0].Payload == '{"a":2,"b":1}'
        assert tick1[1].CityID is None and tick1[1].Payload is None
        assert tick1[0].SimulationEventID < tick1[1].SimulationEventID
        assert tick1[0].SimulationDate == day1
    finally:
        savepoint.rollback()


def _insert_run_raw(cursor) -> int:
    suffix = uuid.uuid4().hex[:8]
    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulationEventsRaw-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestScenarioEventsRaw-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.SimulationRun (ScenarioID, StartSimulationDate, CurrentSimulationDate) "
        "OUTPUT INSERTED.SimulationRunID VALUES (?, '1880-01-01', '1880-01-01')",
        scenario_id,
    )
    return cursor.fetchone()[0]


def test_database_rejects_tick_zero(connection):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.SimulationEvent "
                "(SimulationRunID, SimulationTickID, SimulationDate, EventType) "
                "VALUES (?, 0, '1880-01-01', 'Bad')",
                run_id,
            )
    finally:
        connection.rollback()


def test_database_rejects_non_json_payload(connection):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.SimulationEvent "
                "(SimulationRunID, SimulationTickID, SimulationDate, EventType, Payload) "
                "VALUES (?, 1, '1880-01-01', 'Bad', 'this is not json')",
                run_id,
            )
    finally:
        connection.rollback()


def test_database_rejects_event_for_nonexistent_run(connection):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.SimulationEvent "
                "(SimulationRunID, SimulationTickID, SimulationDate, EventType) "
                "VALUES (-1, 1, '1880-01-01', 'Orphan')"
            )
    finally:
        connection.rollback()
