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
        cursor.execute(
            "DELETE FROM dbo.SimulationRun WHERE ScenarioID IN "
            "(SELECT ScenarioID FROM dbo.Scenario WHERE Name LIKE 'Test%')"
        )
        cursor.execute("DELETE FROM dbo.Scenario WHERE Name LIKE 'Test%'")
        cursor.execute("DELETE FROM dbo.Simulation WHERE Name LIKE 'Test%'")
        cursor.execute("DELETE FROM dbo.City WHERE Name LIKE 'Test%'")
        cursor.execute("DELETE FROM dbo.Region WHERE Name LIKE 'Test%'")
        cursor.execute("DELETE FROM dbo.World WHERE Name LIKE 'Test%'")
        conn.commit()
    except pyodbc.Error:
        conn.rollback()
    finally:
        conn.close()
