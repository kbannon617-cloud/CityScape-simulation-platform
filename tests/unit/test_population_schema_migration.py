"""Unit tests for the 0005 population tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0005_create_population_tables.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_three_batches():
    batches = split_batches(_sql_text())
    assert len(batches) == 3


def test_creates_expected_tables():
    sql = _sql_text()
    for table in ["PopulationGroupType", "PopulationGroup", "ScenarioParameter"]:
        assert re.search(rf"CREATE TABLE dbo\.{table}\s*\(", sql)


def test_population_group_has_foreign_keys_to_city_and_group_type():
    sql = _sql_text()
    assert "REFERENCES dbo.City (CityID)" in sql
    assert "REFERENCES dbo.PopulationGroupType (PopulationGroupTypeID)" in sql


def test_population_group_count_has_non_negative_check_constraint():
    sql = _sql_text()
    assert "CHECK (Count >= 0)" in sql


def test_scenario_parameter_has_foreign_key_to_scenario():
    sql = _sql_text()
    assert "REFERENCES dbo.Scenario (ScenarioID)" in sql


def test_scenario_parameter_key_is_unique_per_scenario():
    sql = _sql_text()
    assert "UQ_ScenarioParameter_ScenarioID_Key UNIQUE (ScenarioID, ParameterKey)" in sql
