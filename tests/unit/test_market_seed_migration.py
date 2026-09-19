"""Unit tests for the 0018 market seed data migration file."""

from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0018_seed_market_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_market_for_cityscape():
    sql = _sql_text()
    assert "INSERT INTO dbo.Market" in sql
    assert "'CityScape'" in sql


def test_seeds_prices_for_all_eleven_resources():
    sql = _sql_text()
    for code in [f"R-{i:03d}" for i in range(1, 12)]:
        assert f"'{code}'" in sql


def test_all_seeded_prices_are_positive():
    """Regression guard: every VALUES row's price must be > 0, matching
    the schema's CK_MarketResourcePrice_UnitPrice_Positive constraint."""
    sql = _sql_text()
    import re

    price_rows = re.findall(r"\('R-\d{3}',\s*([\d.]+)\)", sql)
    assert len(price_rows) == 11
    assert all(float(p) > 0 for p in price_rows)


def test_prices_seeded_against_std_currency():
    sql = _sql_text()
    assert "'STD'" in sql
