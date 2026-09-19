"""Unit tests for the 0017 market tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0017_create_market_tables.sql"
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
    for table in ["Market", "MarketResourcePrice", "MarketTransaction"]:
        assert re.search(rf"CREATE TABLE dbo\.{table}\s*\(", sql)


def test_market_is_unique_per_city():
    sql = _sql_text()
    assert "UQ_Market_CityID UNIQUE (CityID)" in sql


def test_market_resource_price_has_expected_foreign_keys_and_positivity_check():
    sql = _sql_text()
    assert "REFERENCES dbo.Scenario (ScenarioID)" in sql
    assert "REFERENCES dbo.Resource (ResourceID)" in sql
    assert "REFERENCES dbo.Currency (CurrencyID)" in sql
    assert "CHECK (UnitPrice > 0)" in sql


def test_market_transaction_uses_bigint_key_and_has_type_check():
    sql = _sql_text()
    assert "MarketTransactionID BIGINT IDENTITY(1,1)" in sql
    assert "CHECK (TransactionType IN ('Buy', 'Sell'))" in sql


def test_market_transaction_quantity_and_price_must_be_positive():
    sql = _sql_text()
    assert "CHECK (Quantity > 0)" in sql
    assert "CHECK (UnitPrice > 0)" in sql
