"""Unit tests for the 0019 SimulationEvent migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0019_create_simulation_event.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_creates_simulation_event_table():
    assert re.search(r"CREATE TABLE dbo\.SimulationEvent\s*\(", _sql_text())


def test_is_idempotent_via_existence_guard():
    assert "IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SimulationEvent')" in _sql_text()


def test_uses_bigint_key():
    assert "SimulationEventID BIGINT IDENTITY(1,1)" in _sql_text()


def test_tick_is_bigint_and_run_is_int():
    sql = _sql_text()
    assert re.search(r"SimulationTickID\s+BIGINT\s+NOT NULL", sql)
    assert re.search(r"SimulationRunID\s+INT\s+NOT NULL", sql)


def test_has_foreign_keys_to_run_and_city():
    sql = _sql_text()
    assert "REFERENCES dbo.SimulationRun (SimulationRunID)" in sql
    assert "REFERENCES dbo.City (CityID)" in sql


def test_city_is_nullable_for_run_wide_events():
    assert re.search(r"CityID\s+INT\s+NULL", _sql_text())


def test_tick_must_be_positive():
    assert "CHECK (SimulationTickID >= 1)" in _sql_text()


def test_payload_must_be_valid_json_when_present():
    assert "CHECK (Payload IS NULL OR ISJSON(Payload) = 1)" in _sql_text()


def test_has_run_and_tick_index():
    assert "IX_SimulationEvent_Run_Tick ON dbo.SimulationEvent (SimulationRunID, SimulationTickID)" in _sql_text()


def test_does_not_alter_existing_tables():
    assert "ALTER TABLE" not in _sql_text().upper()
