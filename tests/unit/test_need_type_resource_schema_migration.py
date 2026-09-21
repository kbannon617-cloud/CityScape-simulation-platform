"""Unit tests for the 0021 NeedTypeResource schema migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0021_create_need_type_resource.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _code_only() -> str:
    return "\n".join(
        line for line in _sql_text().splitlines() if not line.strip().startswith("--")
    )


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_creates_need_type_resource_table_with_existence_guard():
    code = _code_only()
    assert re.search(r"CREATE TABLE dbo\.NeedTypeResource\s*\(", code)
    assert "IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'NeedTypeResource')" in code


def test_all_columns_are_required():
    code = _code_only()
    assert re.search(r"NeedTypeID\s+INT\s+NOT NULL", code)
    assert re.search(r"ResourceID\s+INT\s+NOT NULL", code)
    assert re.search(r"ConsumptionPriority\s+INT\s+NOT NULL", code)


def test_has_foreign_keys_to_need_type_and_resource():
    code = _code_only()
    assert "REFERENCES dbo.NeedType (NeedTypeID)" in code
    assert "REFERENCES dbo.Resource (ResourceID)" in code


def test_resource_is_unique_per_need_type():
    assert "UNIQUE (NeedTypeID, ResourceID)" in _code_only()


def test_priority_is_unique_per_need_type():
    assert "UNIQUE (NeedTypeID, ConsumptionPriority)" in _code_only()


def test_priority_must_be_positive():
    assert "CHECK (ConsumptionPriority >= 1)" in _code_only()


def test_has_no_unit_column():
    """Unit reconciliation is deferred (ADR-0010 Decision 3)."""
    assert "UnitOfMeasure" not in _code_only()


def test_does_not_alter_existing_tables():
    assert "ALTER TABLE" not in _code_only().upper()
