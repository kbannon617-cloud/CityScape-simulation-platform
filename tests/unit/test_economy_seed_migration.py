"""Unit tests for the 0010 economy seed data migration file."""

from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0010_seed_economy_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_all_seven_category_types():
    sql = _sql_text()
    for code in [
        "OPENING_BALANCE",
        "RESIDENT_INCOME",
        "RESIDENT_EXPENSE",
        "BUILDING_MAINTENANCE",
        "VEHICLE_MAINTENANCE",
        "CONSTRUCTION_COST",
        "VEHICLE_ORDER_COST",
    ]:
        assert f"'{code}'" in sql


def test_seeds_cityscape_treasury_with_placeholder_balance():
    sql = _sql_text()
    assert "10000.00" in sql
    assert "INSERT INTO dbo.Treasury" in sql


def test_seeds_opening_balance_ledger_entry():
    sql = _sql_text()
    assert "INSERT INTO dbo.TreasuryLedgerEntry" in sql
    assert "@OpeningBalanceCategoryID" in sql
