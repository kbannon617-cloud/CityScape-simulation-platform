"""Unit tests for the 0009 economy tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0009_create_economy_tables.sql"
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
    for table in ["TreasuryCategoryType", "Treasury", "TreasuryLedgerEntry"]:
        assert re.search(rf"CREATE TABLE dbo\.{table}\s*\(", sql)


def test_treasury_has_foreign_keys_to_city_and_currency():
    sql = _sql_text()
    assert "REFERENCES dbo.City (CityID)" in sql
    assert "REFERENCES dbo.Currency (CurrencyID)" in sql


def test_treasury_is_unique_per_city():
    sql = _sql_text()
    assert "UQ_Treasury_CityID UNIQUE (CityID)" in sql


def test_treasury_ledger_entry_has_foreign_keys():
    sql = _sql_text()
    assert "REFERENCES dbo.Treasury (TreasuryID)" in sql
    assert "REFERENCES dbo.TreasuryCategoryType (TreasuryCategoryTypeID)" in sql


def test_treasury_ledger_entry_id_is_bigint():
    sql = _sql_text()
    assert re.search(r"TreasuryLedgerEntryID\s+BIGINT IDENTITY\(1,1\)", sql)
