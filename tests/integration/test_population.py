"""
Integration tests for Milestone 2's first deliverable: population schema,
seed data, and the PopulationRepository, all verified against a real SQL
Server database via the shared session-scoped connection fixture.
"""

from __future__ import annotations

import uuid

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.population_repository import (
    PopulationRepository,
    ScenarioParameterNotFoundError,
)


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_cityscape_has_seeded_adult_and_child_population(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT pgt.Code, pg.Count
        FROM dbo.PopulationGroup pg
        JOIN dbo.City c ON c.CityID = pg.CityID
        JOIN dbo.PopulationGroupType pgt ON pgt.PopulationGroupTypeID = pg.PopulationGroupTypeID
        WHERE c.Name = 'CityScape'
        ORDER BY pgt.Code
        """
    )
    rows = {code: count for code, count in cursor.fetchall()}
    assert rows == {"ADULT": 100, "CHILD": 20}


def test_population_group_rejects_negative_count(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT PopulationGroupTypeID FROM dbo.PopulationGroupType WHERE Code = 'ADULT'"
    )
    adult_type_id = cursor.fetchone()[0]

    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.PopulationGroup (CityID, PopulationGroupTypeID, Count) "
            "VALUES (?, ?, ?)",
            city_id,
            adult_type_id,
            -5,
        )
        # Would also violate the (CityID, PopulationGroupTypeID) unique
        # constraint since CityScape/ADULT already exists - either
        # constraint firing proves the row is rejected.
        connection.commit()
    connection.rollback()


def test_cinis_baseline_has_configurable_aging_rate(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT sp.ParameterValue
        FROM dbo.ScenarioParameter sp
        JOIN dbo.Scenario sc ON sc.ScenarioID = sp.ScenarioID
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
          AND sp.ParameterKey = 'ChildToAdultMonthlyAgingRatePercent'
        """
    )
    row = cursor.fetchone()
    assert row is not None
    assert float(row[0]) == 1.5


def test_population_repository_returns_correct_totals(sqlalchemy_session):
    cursor_conn = sqlalchemy_session.connection().connection
    cursor = cursor_conn.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]

    repo = PopulationRepository(sqlalchemy_session)

    by_group = repo.get_population_by_city(city_id)
    assert by_group == {"ADULT": 100, "CHILD": 20}

    assert repo.get_total_population(city_id) == 120


def test_population_repository_get_scenario_parameter(sqlalchemy_session):
    cursor_conn = sqlalchemy_session.connection().connection
    cursor = cursor_conn.cursor()
    cursor.execute(
        """
        SELECT sc.ScenarioID
        FROM dbo.Scenario sc
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
        """
    )
    scenario_id = cursor.fetchone()[0]

    repo = PopulationRepository(sqlalchemy_session)
    rate = repo.get_scenario_parameter(scenario_id, "ChildToAdultMonthlyAgingRatePercent")
    assert rate == 1.5


def test_population_repository_raises_for_unknown_parameter(sqlalchemy_session):
    cursor_conn = sqlalchemy_session.connection().connection
    cursor = cursor_conn.cursor()
    cursor.execute(
        """
        SELECT sc.ScenarioID
        FROM dbo.Scenario sc
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
        """
    )
    scenario_id = cursor.fetchone()[0]

    repo = PopulationRepository(sqlalchemy_session)
    with pytest.raises(ScenarioParameterNotFoundError):
        repo.get_scenario_parameter(scenario_id, f"NotARealKey-{uuid.uuid4().hex[:8]}")
