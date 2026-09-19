"""Unit tests for the 0015 vehicle tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0015_create_vehicle_tables.sql"
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
    for table in ["VehicleType", "TransportMode", "BuildingVehicleRequirement", "CityVehicle"]:
        assert re.search(rf"CREATE TABLE dbo\.{table}\s*\(", sql)


def test_transport_mode_has_foreign_key_to_vehicle_type():
    sql = _sql_text()
    assert "REFERENCES dbo.VehicleType (VehicleTypeID)" in sql


def test_building_vehicle_requirement_has_expected_foreign_keys():
    sql = _sql_text()
    assert "REFERENCES dbo.BuildingType (BuildingTypeID)" in sql
    assert "UQ_BuildingVehicleRequirement_BuildingType_VehicleType UNIQUE (BuildingTypeID, VehicleTypeID)" in sql


def test_city_vehicle_has_non_negative_check_and_city_fk():
    sql = _sql_text()
    assert "CHECK (Count >= 0)" in sql
    assert "REFERENCES dbo.City (CityID)" in sql
