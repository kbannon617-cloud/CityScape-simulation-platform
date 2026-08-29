"""Unit tests for the 0002 core reference tables migration file itself.

These check the raw SQL text and batch structure, catching typos or
missing GO separators without needing a live SQL Server connection.
Live-database verification lives in tests/integration/test_core_schema.py.
"""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0002_create_core_reference_tables.sql"
)

EXPECTED_TABLES = [
    "Currency",
    "UnitOfMeasure",
    "World",
    "Region",
    "City",
    "Simulation",
    "Scenario",
    "SimulationRun",
]


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_one_batch_per_table():
    batches = split_batches(_sql_text())
    assert len(batches) == len(EXPECTED_TABLES)


def test_every_expected_table_is_created():
    sql = _sql_text()
    for table_name in EXPECTED_TABLES:
        assert re.search(rf"CREATE TABLE dbo\.{table_name}\s*\(", sql), (
            f"Expected a CREATE TABLE statement for {table_name}"
        )


def test_foreign_keys_reference_expected_parent_tables():
    sql = _sql_text()
    assert "REFERENCES dbo.World (WorldID)" in sql
    assert "REFERENCES dbo.Region (RegionID)" in sql
    assert "REFERENCES dbo.Simulation (SimulationID)" in sql
    assert "REFERENCES dbo.Scenario (ScenarioID)" in sql


def test_current_simulation_tick_id_is_bigint():
    sql = _sql_text()
    assert re.search(r"CurrentSimulationTickID\s+BIGINT", sql)


def test_reference_tables_use_int_identity():
    sql = _sql_text()
    for table_name in EXPECTED_TABLES:
        id_column = f"{table_name}ID"
        assert re.search(rf"{id_column}\s+INT IDENTITY\(1,1\)", sql), (
            f"Expected {id_column} to be an INT IDENTITY primary key"
        )
