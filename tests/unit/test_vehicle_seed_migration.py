"""Unit tests for the 0016 vehicle seed data migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0016_seed_vehicle_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_two_vehicle_types():
    sql = _sql_text()
    assert "'V-001', 'Boat'" in sql
    assert "'V-002', 'Cart'" in sql


def test_seeds_one_transport_mode():
    sql = _sql_text()
    assert "'TM-001'" in sql
    assert "'Dirt Road'" in sql


def test_seeds_building_vehicle_requirements_for_trout_fishery_and_teamster_depot():
    sql = _sql_text()
    assert "'Trout Fishery'" in sql
    assert "'Teamster Depot'" in sql


def test_does_not_seed_any_city_vehicle_rows():
    """CityScape genuinely owns 0 vehicles right now (0 Trout Fisheries,
    0 Teamster Depots per the workbook's own Vehicle Assignments data) -
    this migration must not insert into CityVehicle at all."""
    sql = _sql_text()
    assert "INSERT INTO dbo.CityVehicle" not in sql
