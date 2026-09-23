"""
Integration tests for the ConstructionProject table (migrations 0023/0024)
against real SQL Server.

Constraint tests use an uncommitted raw transaction, rolled back in a
finally block. Nothing here shares a session across multiple commits -
each test uses one connection/transaction only, per the safe pattern
this suite settled on after the Step 4.4c incident.
"""

from __future__ import annotations

import datetime

import pyodbc
import pytest

D = datetime.date

INSERT_SQL = """
INSERT INTO dbo.ConstructionProject (
    CityID, BuildingTypeID, BuildingsOrdered, OrderSimulationDate,
    TotalConstructionCost, TotalTimberRequired, TotalStoneRequired,
    AdjustedDurationMonths, MonthsElapsed, Status, CompletedSimulationDate
)
SELECT TOP 1
    c.CityID, bt.BuildingTypeID, ?, ?, ?, ?, ?, ?, ?, ?, ?
FROM dbo.City c, dbo.BuildingType bt
WHERE c.Name = 'CityScape' AND bt.Code = 'B-002'
"""


def _insert(cursor, **overrides):
    params = {
        "buildings_ordered": 1,
        "order_date": D(1880, 2, 1),
        "cost": "100.0000",
        "timber": "10.0000",
        "stone": "5.0000",
        "duration": 1,
        "elapsed": 0,
        "status": "InProgress",
        "completed_date": None,
    }
    params.update(overrides)
    cursor.execute(
        INSERT_SQL,
        params["buildings_ordered"],
        params["order_date"],
        params["cost"],
        params["timber"],
        params["stone"],
        params["duration"],
        params["elapsed"],
        params["status"],
        params["completed_date"],
    )


def test_table_foreign_keys_index_and_checks_exist(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'ConstructionProject'")
    assert cursor.fetchone()[0] == 1

    cursor.execute(
        "SELECT name FROM sys.foreign_keys "
        "WHERE parent_object_id = OBJECT_ID('dbo.ConstructionProject')"
    )
    assert {row[0] for row in cursor.fetchall()} == {
        "FK_ConstructionProject_City",
        "FK_ConstructionProject_BuildingType",
    }

    cursor.execute(
        "SELECT name FROM sys.check_constraints "
        "WHERE parent_object_id = OBJECT_ID('dbo.ConstructionProject')"
    )
    assert {row[0] for row in cursor.fetchall()} == {
        "CK_ConstructionProject_BuildingsOrdered_Positive",
        "CK_ConstructionProject_AdjustedDurationMonths_Positive",
        "CK_ConstructionProject_MonthsElapsed_NonNegative",
        "CK_ConstructionProject_Status",
        "CK_ConstructionProject_Completed_Consistency",
    }

    cursor.execute(
        "SELECT name, is_unique FROM sys.indexes "
        "WHERE object_id = OBJECT_ID('dbo.ConstructionProject') AND name = 'IX_ConstructionProject_City_Status'"
    )
    name, is_unique = cursor.fetchone()
    assert (name, bool(is_unique)) == ("IX_ConstructionProject_City_Status", False)
    connection.rollback()


def test_database_accepts_a_valid_in_progress_row(connection):
    cursor = connection.cursor()
    try:
        _insert(cursor)
        assert cursor.rowcount == 1
    finally:
        connection.rollback()


def test_database_accepts_a_valid_complete_row(connection):
    cursor = connection.cursor()
    try:
        _insert(
            cursor,
            status="Complete",
            elapsed=1,
            completed_date=D(1880, 3, 1),
        )
        assert cursor.rowcount == 1
    finally:
        connection.rollback()


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"buildings_ordered": 0}, "zero buildings ordered"),
        ({"buildings_ordered": -1}, "negative buildings ordered"),
        ({"duration": 0}, "zero adjusted duration"),
        ({"elapsed": -1}, "negative months elapsed"),
        ({"status": "Cancelled"}, "an unrecognized status"),
        ({"status": "Complete", "completed_date": None}, "Complete with no completed date"),
        (
            {"status": "InProgress", "completed_date": D(1880, 3, 1)},
            "InProgress with a completed date set",
        ),
    ],
)
def test_database_rejects_invalid_rows(connection, overrides, reason):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            _insert(cursor, **overrides)
    finally:
        connection.rollback()


def test_database_rejects_a_nonexistent_city_or_building_type(connection):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.ConstructionProject ("
                "CityID, BuildingTypeID, BuildingsOrdered, OrderSimulationDate, "
                "TotalConstructionCost, TotalTimberRequired, TotalStoneRequired, "
                "AdjustedDurationMonths, MonthsElapsed, Status, CompletedSimulationDate"
                ") VALUES (-1, -1, 1, '1880-02-01', 100, 10, 5, 1, 0, 'InProgress', NULL)"
            )
    finally:
        connection.rollback()


def test_a_city_may_have_more_than_one_construction_project_over_time(connection):
    """The table itself allows multiple rows per city (any status); the
    concurrent-InProgress limit is a service-layer rule (ADR-0011), not a
    database constraint - so two Complete rows for the same city must be
    accepted here."""
    cursor = connection.cursor()
    try:
        _insert(cursor, status="Complete", elapsed=1, completed_date=D(1880, 3, 1))
        _insert(cursor, status="Complete", elapsed=1, completed_date=D(1880, 4, 1))
    finally:
        connection.rollback()


def test_seeded_construction_scenario_parameters_exist(connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT sp.ParameterKey, sp.ParameterValue "
        "FROM dbo.ScenarioParameter sp "
        "JOIN dbo.Scenario sc ON sc.ScenarioID = sp.ScenarioID "
        "JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID "
        "WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline' "
        "AND sp.ParameterKey IN ("
        "'MonthlyConstructionBudget', 'ConstructionBonusPerCompletedCrew', "
        "'MaxActiveConstructionProjectsPerCity')"
    )
    values = {code: float(value) for code, value in cursor.fetchall()}
    connection.rollback()

    assert values == {
        "MonthlyConstructionBudget": 100.0,
        "ConstructionBonusPerCompletedCrew": 0.0005,
        "MaxActiveConstructionProjectsPerCity": 1.0,
    }
