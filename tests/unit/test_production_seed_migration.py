"""Unit tests for the 0012 production seed data migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0012_seed_production_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_eleven_resources():
    sql = _sql_text()
    for code in [f"R-{i:03d}" for i in range(1, 12)]:
        assert f"'{code}'" in sql


def test_seeds_flax_eggs_ore_with_corrected_ids():
    """The resource ID fix confirmed by the project owner (2026-09-13):
    Production Flows Catalog is authoritative. R-008=Flax, R-009=Eggs,
    R-010=Lentils, R-011=Ore."""
    sql = _sql_text()
    assert "('R-008', 'Flax'" in sql
    assert "('R-009', 'Eggs'" in sql
    assert "('R-011', 'Ore'" in sql


def test_seeds_fifteen_building_types():
    sql = _sql_text()
    for code in [f"B-{i:03d}" for i in range(1, 16)]:
        assert f"'{code}'" in sql


def test_seeds_cottage_starting_count_of_three():
    sql = _sql_text()
    assert "@CottageTypeID, 3" in sql


def test_seeds_wheat_farm_starting_count_of_one():
    """Regression test for a real bug found during review: the initial
    draft only seeded Cottage's starting count and silently omitted Wheat
    Farm, which also starts at 1 per the workbook's actual data."""
    sql = _sql_text()
    assert "@WheatFarmTypeID" in sql
    assert "@WheatFarmTypeID, 1" in sql


def test_seeds_eleven_production_flows():
    sql = _sql_text()
    for code in [f"BF-{i:03d}" for i in range(1, 12)]:
        assert f"'{code}'" in sql


def test_saw_mill_has_both_an_input_and_an_output_flow():
    sql = _sql_text()
    assert "'BF-005', 'B-009', 'Output', 'R-005'" in sql
    assert "'BF-008', 'B-009', 'Input',  'R-004'" in sql
