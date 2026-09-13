"""Unit tests for the 0007 needs tables migration file."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0007_create_needs_tables.sql"
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
    assert re.search(r"CREATE TABLE dbo\.NeedType\s*\(", sql)
    assert re.search(r"CREATE TABLE dbo\.NeedConsumptionRate\s*\(", sql)


def test_need_consumption_rate_has_expected_foreign_keys():
    sql = _sql_text()
    assert "REFERENCES dbo.PopulationGroupType (PopulationGroupTypeID)" in sql
    assert "REFERENCES dbo.NeedType (NeedTypeID)" in sql
    assert "REFERENCES dbo.UnitOfMeasure (UnitOfMeasureID)" in sql


def test_need_consumption_rate_has_non_negative_check():
    sql = _sql_text()
    assert "CHECK (QuantityPerPersonPerDay >= 0)" in sql


def test_need_consumption_rate_unique_per_group_and_need():
    sql = _sql_text()
    assert "UQ_NeedConsumptionRate_GroupType_NeedType UNIQUE (PopulationGroupTypeID, NeedTypeID)" in sql
