"""Unit tests for the 0026 CitySnapshot migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0026_create_city_snapshot.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _code_only() -> str:
    return "\n".join(
        line for line in _sql_text().splitlines() if not line.strip().startswith("--")
    )


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_creates_table_with_existence_guard():
    code = _code_only()
    assert re.search(r"CREATE TABLE dbo\.CitySnapshot\s*\(", code)
    assert "IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CitySnapshot')" in code


def test_uses_bigint_key_and_tick():
    code = _code_only()
    assert re.search(r"CitySnapshotID\s+BIGINT IDENTITY\(1,1\)", code)
    assert re.search(r"SimulationTickID\s+BIGINT\s+NOT NULL", code)


def test_has_foreign_keys_to_run_and_city():
    code = _code_only()
    assert "REFERENCES dbo.SimulationRun (SimulationRunID)" in code
    assert "REFERENCES dbo.City (CityID)" in code


def test_city_id_is_required_unlike_simulation_events_optional_city():
    assert re.search(r"CityID\s+INT\s+NOT NULL", _code_only())


def test_payload_is_required_and_must_be_valid_json():
    code = _code_only()
    assert re.search(r"Payload\s+NVARCHAR\(MAX\)\s+NOT NULL", code)
    assert "CHECK (ISJSON(Payload) = 1)" in code


def test_tick_must_be_positive():
    assert "CHECK (SimulationTickID >= 1)" in _code_only()


def test_has_run_and_tick_index():
    assert "IX_CitySnapshot_Run_Tick ON dbo.CitySnapshot (SimulationRunID, SimulationTickID)" in _code_only()


def test_does_not_alter_existing_tables():
    assert "ALTER TABLE" not in _code_only().upper()
