"""
Shared fixtures for integration tests. All integration-test-created rows
are named with a "Test" prefix; the session-scoped cleanup below relies on
that convention to remove them afterward, in FK-safe order, so tests never
leave permanent pollution in a database also used for real development.
"""

from __future__ import annotations

from pathlib import Path

import pyodbc
import pytest

from cinis.config.settings import ConfigurationError, load_database_settings
from cinis.database.migration_runner import run_pending_migrations

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def _connect() -> pyodbc.Connection:
    settings = load_database_settings()
    if settings.auth_mode == "windows":
        conn_str = (
            f"DRIVER={{{settings.driver}}};SERVER={settings.server};"
            f"DATABASE={settings.database};Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{settings.driver}}};SERVER={settings.server};"
            f"DATABASE={settings.database};UID={settings.user};PWD={settings.password};"
        )
    return pyodbc.connect(conn_str, timeout=5)



def _cleanup_test_rows(cursor) -> None:
    """Delete every row created by integration tests (names prefixed
    "Test"), in FK-safe order. Does not commit; the caller owns the
    transaction. Raises pyodbc.Error on any failure, so a broken statement
    is visible to whoever calls this directly.

    ORDER RULE: a table must be deleted before every table it references.
    tests/unit/test_cleanup_coverage.py derives the FK graph from the
    migrations and fails if a table that references one of these tables is
    missing here, or is deleted after its parent.

    OWNERSHIP RULE: a "Test%" Simulation owns ALL of its Scenarios,
    whatever they are named. The earliest M1 tests created Test-named
    Simulations holding Scenarios named "BaseScenario-..." and
    "Scenario2-...". A name-only Scenario match skipped those, the
    Simulation delete then failed on FK_Scenario_Simulation, and because
    the session-end cleanup swallows pyodbc.Error that silently skipped the
    ENTIRE cleanup in every session (found in M5 Step 5.1: 157 Test
    Simulations and 109 Test Cities had accumulated).
    """
    # Rows that reference a test SimulationRun (or a test City's
    # inventory) must be deleted first; otherwise the FK error would
    # roll back this whole cleanup.
    test_simulations = "(SELECT SimulationID FROM dbo.Simulation WHERE Name LIKE 'Test%')"
    test_scenarios_now = (
        "(SELECT ScenarioID FROM dbo.Scenario WHERE Name LIKE 'Test%' "
        "OR SimulationID IN " + test_simulations + ")"
    )
    test_runs = (
        "(SELECT SimulationRunID FROM dbo.SimulationRun WHERE ScenarioID IN "
        + test_scenarios_now
        + ")"
    )
    test_city_inventory = (
        "(SELECT CityInventoryID FROM dbo.CityInventory WHERE CityID IN "
        "(SELECT CityID FROM dbo.City WHERE Name LIKE 'Test%'))"
    )
    test_cities = "(SELECT CityID FROM dbo.City WHERE Name LIKE 'Test%')"
    test_markets = "(SELECT MarketID FROM dbo.Market WHERE CityID IN " + test_cities + ")"
    test_treasuries = "(SELECT TreasuryID FROM dbo.Treasury WHERE CityID IN " + test_cities + ")"

    # Step 4.7's multi-day test was the first to leave real, committed
    # Population/Building/CityVehicle/ConstructionProject/CitySnapshot/
    # ScenarioParameter rows against a Test city/scenario; M5 Step 5.1 adds
    # the Market family (MarketTransaction -> Market, MarketResourcePrice),
    # which the first vertical-slice test commits for real.
    cursor.execute("DELETE FROM dbo.CitySnapshot WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.ConstructionProject WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.Building WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.CityVehicle WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.PopulationGroup WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.MarketTransaction WHERE MarketID IN " + test_markets)
    cursor.execute("DELETE FROM dbo.Market WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.MarketResourcePrice WHERE ScenarioID IN " + test_scenarios_now)
    cursor.execute("DELETE FROM dbo.ScenarioParameter WHERE ScenarioID IN " + test_scenarios_now)

    cursor.execute(
        "DELETE FROM dbo.InventoryLedgerEntry WHERE SimulationRunID IN "
        + test_runs
        + " OR CityInventoryID IN "
        + test_city_inventory
    )
    # Also matches untraced entries (SimulationRunID IS NULL, e.g. a command
    # issued outside a tick) belonging to a Test city's Treasury; the
    # run-only match used before left those behind and blocked the
    # Treasury delete below.
    cursor.execute(
        "DELETE FROM dbo.TreasuryLedgerEntry WHERE SimulationRunID IN "
        + test_runs
        + " OR TreasuryID IN "
        + test_treasuries
    )
    # Treasury must come after TreasuryLedgerEntry above: it is
    # referenced by that table, not referencing it.
    cursor.execute("DELETE FROM dbo.Treasury WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.CityInventory WHERE CityID IN " + test_cities)
    cursor.execute("DELETE FROM dbo.SimulationEvent WHERE SimulationRunID IN " + test_runs)
    cursor.execute("DELETE FROM dbo.SimulationRun WHERE ScenarioID IN " + test_scenarios_now)
    cursor.execute("DELETE FROM dbo.Scenario WHERE ScenarioID IN " + test_scenarios_now)
    cursor.execute("DELETE FROM dbo.Simulation WHERE Name LIKE 'Test%'")
    cursor.execute("DELETE FROM dbo.City WHERE Name LIKE 'Test%'")
    cursor.execute("DELETE FROM dbo.Region WHERE Name LIKE 'Test%'")
    cursor.execute("DELETE FROM dbo.World WHERE Name LIKE 'Test%'")


@pytest.fixture
def cleanup_test_rows():
    """The session-end cleanup, exposed so a test can prove it works (see
    test_cleanup_of_test_rows.py). Takes a pyodbc cursor; does not commit."""
    return _cleanup_test_rows

@pytest.fixture(scope="session")
def connection():
    try:
        conn = _connect()
    except (ConfigurationError, pyodbc.Error) as exc:
        pytest.skip(f"No live SQL Server available for integration tests: {exc}")
        return

    run_pending_migrations(conn, MIGRATIONS_DIR)

    yield conn

    cursor = conn.cursor()
    try:
        _cleanup_test_rows(cursor)
        conn.commit()
    except pyodbc.Error:
        # Known technical debt (M5 decision): this swallows the error, so a
        # cleanup failure leaves every Test row behind with no message. The
        # static coverage test (tests/unit/test_cleanup_coverage.py) and the
        # live test (tests/integration/test_cleanup_of_test_rows.py) exist
        # so a broken cleanup is caught before it can fail silently here.
        conn.rollback()
    finally:
        conn.close()
