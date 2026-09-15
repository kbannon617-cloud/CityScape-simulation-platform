"""Unit tests for the 0013 inventory tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0013_create_inventory_tables.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_two_batches():
    batches = split_batches(_sql_text())
    assert len(batches) == 2


def test_creates_expected_tables():
    sql = _sql_text()
    assert re.search(r"CREATE TABLE dbo\.CityInventory\s*\(", sql)
    assert re.search(r"CREATE TABLE dbo\.InventoryLedgerEntry\s*\(", sql)


def test_city_inventory_has_non_negative_quantity_check():
    """Document 7's first-class invariant: non-negative inventory."""
    sql = _sql_text()
    assert "CHECK (Quantity >= 0)" in sql


def test_city_inventory_unique_per_city_and_resource():
    sql = _sql_text()
    assert "UQ_CityInventory_City_Resource UNIQUE (CityID, ResourceID)" in sql


def test_inventory_ledger_entry_uses_bigint_key():
    sql = _sql_text()
    assert "InventoryLedgerEntryID BIGINT IDENTITY(1,1)" in sql


def test_inventory_ledger_entry_has_foreign_key_to_city_inventory():
    sql = _sql_text()
    assert "REFERENCES dbo.CityInventory (CityInventoryID)" in sql
