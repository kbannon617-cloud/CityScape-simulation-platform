"""Unit tests for the 0004 filtered-unique-index migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0004_enforce_single_primary_active_city.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    batches = split_batches(_sql_text())
    assert len(batches) == 1


def test_creates_unique_filtered_index_on_city_isprimaryactive():
    sql = _sql_text()
    assert "CREATE UNIQUE INDEX UQ_City_OnePrimaryActive" in sql
    assert "ON dbo.City (IsPrimaryActive)" in sql
    assert "WHERE IsPrimaryActive = 1" in sql
