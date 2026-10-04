"""Unit tests for the 0025 market transaction categories seed migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0025_seed_market_transaction_categories.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_seeds_both_categories():
    sql = _sql_text()
    assert "'MARKET_PURCHASE', 'Market Purchase'" in sql
    assert "'MARKET_SALE', 'Market Sale'" in sql


def test_every_insert_is_guarded_for_safe_rerun():
    assert _sql_text().count("IF NOT EXISTS (") == 2


def test_is_additive_only():
    sql = _sql_text().upper()
    for forbidden in ("DROP ", "UPDATE ", "DELETE ", "ALTER ", "TRUNCATE", "CREATE TABLE"):
        assert forbidden not in sql
