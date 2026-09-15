"""Unit tests for the 0014 inventory seed data migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0014_seed_inventory_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_wheat_and_timber_only():
    sql = _sql_text()
    assert "'R-001'" in sql  # Wheat
    assert "'R-004'" in sql  # Timber


def test_seeds_100_units_of_each():
    sql = _sql_text()
    assert "100.00" in sql


def test_records_opening_stock_via_ledger():
    sql = _sql_text()
    assert "INSERT INTO dbo.InventoryLedgerEntry" in sql
    assert "'Opening stock.'" in sql


def test_uses_same_start_date_as_treasury_opening_balance():
    sql = _sql_text()
    assert "'2026-01-01'" in sql
