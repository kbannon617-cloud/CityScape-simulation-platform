"""Unit tests for the 0011 production tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0011_create_production_tables.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_four_batches():
    batches = split_batches(_sql_text())
    assert len(batches) == 4


def test_creates_expected_tables():
    sql = _sql_text()
    for table in ["Resource", "BuildingType", "Building", "ProductionFlow"]:
        assert re.search(rf"CREATE TABLE dbo\.{table}\s*\(", sql)


def test_resource_has_unit_of_measure_foreign_key():
    sql = _sql_text()
    assert "REFERENCES dbo.UnitOfMeasure (UnitOfMeasureID)" in sql


def test_resource_population_food_status_is_tri_state():
    sql = _sql_text()
    assert "CHECK (PopulationFoodStatus IN ('Yes', 'No', 'Future'))" in sql


def test_building_type_does_not_have_monthly_output_columns():
    """Confirms the deliberate design decision: BuildingType must not
    duplicate what ProductionFlow already tracks."""
    sql = _sql_text()
    assert "MonthlyOutput" not in sql
    assert "OutputResource" not in sql


def test_building_has_foreign_keys_to_city_and_building_type():
    sql = _sql_text()
    assert "REFERENCES dbo.City (CityID)" in sql
    assert "REFERENCES dbo.BuildingType (BuildingTypeID)" in sql


def test_production_flow_has_foreign_keys_and_flow_type_check():
    sql = _sql_text()
    assert "REFERENCES dbo.BuildingType (BuildingTypeID)" in sql
    assert "REFERENCES dbo.Resource (ResourceID)" in sql
    assert "CHECK (FlowType IN ('Input', 'Output'))" in sql
