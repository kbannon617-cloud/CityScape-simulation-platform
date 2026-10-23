"""
Integration tests for the CitySnapshot table (migration 0026) and
SnapshotRepository, run against real SQL Server. Mirrors
test_simulation_events.py's scaffold exactly.
"""

from __future__ import annotations

import datetime
import uuid

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.models.simulation import CitySnapshot, Scenario, Simulation, SimulationRun
from cinis.repositories.snapshot_repository import SnapshotRepository

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
    simulation = Simulation(Name=f"TestSimulationSnapshot-{suffix}")
    session.add(simulation)
    session.flush()
    scenario = Scenario(SimulationID=simulation.SimulationID, Name=f"TestScenarioSnapshot-{suffix}")
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


def test_city_snapshot_table_and_constraints_exist(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'CitySnapshot'")
    assert cursor.fetchone()[0] == 1

    cursor.execute(
        "SELECT name FROM sys.check_constraints "
        "WHERE parent_object_id = OBJECT_ID('dbo.CitySnapshot')"
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {
        "CK_CitySnapshot_SimulationTickID_Positive",
        "CK_CitySnapshot_Payload_IsJson",
    }


def test_record_snapshot_round_trips_a_real_payload(sqlalchemy_session, cityscape_id):
    savepoint = sqlalchemy_session.begin_nested()
    try:
        run = _create_run(sqlalchemy_session)
        repo = SnapshotRepository(sqlalchemy_session)

        repo.record_snapshot(
            simulation_run_id=run.SimulationRunID,
            simulation_tick_id=30,
            simulation_date=datetime.date(1880, 2, 1),
            city_id=cityscape_id,
            payload={"AdultCount": 100, "ChildCount": 20},
        )
        sqlalchemy_session.flush()

        snapshot = (
            sqlalchemy_session.query(CitySnapshot)
            .filter(CitySnapshot.SimulationRunID == run.SimulationRunID)
            .one()
        )
        assert snapshot.SimulationTickID == 30
        assert snapshot.CityID == cityscape_id
        assert snapshot.Payload == '{"AdultCount":100,"ChildCount":20}'
    finally:
        savepoint.rollback()


def test_database_rejects_non_json_payload(connection):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.CitySnapshot "
                "(SimulationRunID, SimulationTickID, SimulationDate, CityID, Payload) "
                "SELECT ?, 1, '1880-01-01', CityID, 'not json' FROM dbo.City WHERE Name = 'CityScape'",
                run_id,
            )
    finally:
        connection.rollback()


def test_database_rejects_tick_zero(connection):
    cursor = connection.cursor()
    try:
        run_id = _insert_run_raw(cursor)
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.CitySnapshot "
                "(SimulationRunID, SimulationTickID, SimulationDate, CityID, Payload) "
                "SELECT ?, 0, '1880-01-01', CityID, '{}' FROM dbo.City WHERE Name = 'CityScape'",
                run_id,
            )
    finally:
        connection.rollback()


def _insert_run_raw(cursor) -> int:
    suffix = uuid.uuid4().hex[:8]
    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulationSnapshotRaw-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestScenarioSnapshotRaw-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO dbo.SimulationRun (ScenarioID, StartSimulationDate, CurrentSimulationDate) "
        "OUTPUT INSERTED.SimulationRunID VALUES (?, '1880-01-01', '1880-01-01')",
        scenario_id,
    )
    return cursor.fetchone()[0]
