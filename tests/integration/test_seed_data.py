"""
Integration tests verifying the 0003 seed data migration against a real
SQL Server instance.

The shared `connection` fixture (see tests/integration/conftest.py) applies
migrations once per session and handles cleanup afterward.
"""

from __future__ import annotations

from pathlib import Path

from cinis.database.migration_runner import run_pending_migrations

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def test_standard_currency_seeded(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT Name FROM dbo.Currency WHERE Code = 'STD'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Standard Currency"


def test_baseline_units_of_measure_seeded(connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT Code FROM dbo.UnitOfMeasure WHERE Code IN ('KG', 'TON', 'L', 'EA')"
    )
    codes = {row[0] for row in cursor.fetchall()}
    assert codes == {"KG", "TON", "L", "EA"}


def test_cityscape_is_the_one_primary_active_city(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT Name FROM dbo.City WHERE IsPrimaryActive = 1")
    rows = cursor.fetchall()
    assert len(rows) == 1, "MVP scope requires exactly one primary active city"
    assert rows[0][0] == "CityScape"


def test_cityscape_belongs_to_primary_region_and_world(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT w.Name, r.Name, c.Name
        FROM dbo.City c
        JOIN dbo.Region r ON r.RegionID = c.RegionID
        JOIN dbo.World w ON w.WorldID = r.WorldID
        WHERE c.Name = 'CityScape'
        """
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Primary World"
    assert row[1] == "Primary Region"
    assert row[2] == "CityScape"


def test_cinis_baseline_scenario_seeded(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT s.Name, sc.Name, sc.ParentScenarioID
        FROM dbo.Scenario sc
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
        """
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[2] is None, "Cinis Baseline should be a base scenario with no parent"


def test_seed_migration_is_idempotent_on_rerun(connection):
    """Running the (already-applied) migrations again must not duplicate seed rows."""
    run_pending_migrations(connection, MIGRATIONS_DIR)  # no-op, already applied

    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.City WHERE Name = 'CityScape'")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT COUNT(*) FROM dbo.Currency WHERE Code = 'STD'")
    assert cursor.fetchone()[0] == 1
