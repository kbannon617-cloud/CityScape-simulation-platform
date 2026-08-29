"""
Integration tests for the 0002 core reference tables migration, run against
a real SQL Server instance.

The shared `connection` fixture (see tests/integration/conftest.py) applies
migrations once per session and cleans up any "Test"-prefixed rows this
suite creates afterward.
"""

from __future__ import annotations

import uuid

import pyodbc
import pytest

CORE_TABLES = [
    "Currency",
    "UnitOfMeasure",
    "World",
    "Region",
    "City",
    "Simulation",
    "Scenario",
    "SimulationRun",
]


def test_all_core_tables_exist(connection):
    cursor = connection.cursor()
    for table_name in CORE_TABLES:
        cursor.execute("SELECT 1 FROM sys.tables WHERE name = ?", table_name)
        assert cursor.fetchone() is not None, f"Expected table {table_name} to exist"


def test_region_requires_valid_world_id(connection):
    cursor = connection.cursor()
    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.Region (WorldID, Name) VALUES (?, ?)",
            -999999,
            f"TestBadRegion-{uuid.uuid4().hex[:8]}",
        )
        connection.commit()
    connection.rollback()


def test_world_region_city_chain_inserts_successfully(connection):
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]

    cursor.execute(
        "INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)",
        f"TestWorld-{suffix}",
    )
    world_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
        world_id,
        f"TestRegion-{suffix}",
    )
    region_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) "
        "OUTPUT INSERTED.CityID VALUES (?, ?, ?)",
        region_id,
        f"TestCity-{suffix}",
        0,  # Must never be 1: MVP scope allows exactly one primary active
        #     city, and that city is the real seeded "CityScape", not
        #     test-created data.
    )
    city_id = cursor.fetchone()[0]
    connection.commit()

    assert city_id is not None


def test_scenario_allows_null_parent_for_base_scenario(connection):
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]

    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulation-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestBaseScenario-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    connection.commit()

    assert scenario_id is not None


def test_simulation_run_status_check_constraint_rejects_invalid_status(connection):
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]

    cursor.execute(
        "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
        f"TestSimulation2-{suffix}",
    )
    simulation_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name) "
        "OUTPUT INSERTED.ScenarioID VALUES (?, NULL, ?)",
        simulation_id,
        f"TestScenario2-{suffix}",
    )
    scenario_id = cursor.fetchone()[0]
    connection.commit()

    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.SimulationRun "
            "(ScenarioID, StartSimulationDate, CurrentSimulationDate, Status) "
            "VALUES (?, '2026-01-01', '2026-01-01', 'NotARealStatus')",
            scenario_id,
        )
        connection.commit()
    connection.rollback()
