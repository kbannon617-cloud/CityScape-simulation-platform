"""Unit tests for the 0023 ConstructionProject migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0023_create_construction_project.sql"
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
    assert re.search(r"CREATE TABLE dbo\.ConstructionProject\s*\(", code)
    assert "IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ConstructionProject')" in code


def test_has_foreign_keys_to_city_and_building_type():
    code = _code_only()
    assert "REFERENCES dbo.City (CityID)" in code
    assert "REFERENCES dbo.BuildingType (BuildingTypeID)" in code


def test_snapshot_columns_are_required():
    code = _code_only()
    for column in (
        "TotalConstructionCost",
        "TotalTimberRequired",
        "TotalStoneRequired",
        "AdjustedDurationMonths",
    ):
        assert re.search(rf"{column}\s+(DECIMAL|INT)\S*\s+NOT NULL", code), column


def test_buildings_ordered_must_be_positive():
    assert "CHECK (BuildingsOrdered >= 1)" in _code_only()


def test_duration_must_be_positive():
    assert "CHECK (AdjustedDurationMonths >= 1)" in _code_only()


def test_months_elapsed_defaults_to_zero_and_cannot_be_negative():
    code = _code_only()
    assert "DEFAULT 0" in code
    assert "CHECK (MonthsElapsed >= 0)" in code


def test_status_is_constrained_to_the_two_known_values():
    assert "CHECK (Status IN ('InProgress', 'Complete'))" in _code_only()


def test_completed_date_consistency_check_exists():
    code = _code_only()
    assert "Status = 'InProgress' AND CompletedSimulationDate IS NULL" in code
    assert "Status = 'Complete' AND CompletedSimulationDate IS NOT NULL" in code


def test_index_on_city_and_status_is_not_unique():
    code = _code_only()
    assert "CREATE NONCLUSTERED INDEX IX_ConstructionProject_City_Status" in code
    assert "CREATE UNIQUE" not in code.upper()


def test_does_not_alter_existing_tables():
    assert "ALTER TABLE" not in _code_only().upper()
