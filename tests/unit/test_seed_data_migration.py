"""Unit tests for the 0003 seed data migration file itself (no live DB needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0003_seed_cinis_reference_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_four_batches():
    # Currency | UnitOfMeasure | Geography | Simulation+Scenario
    batches = split_batches(_sql_text())
    assert len(batches) == 4


def test_seeds_standard_currency():
    sql = _sql_text()
    assert "'STD'" in sql
    assert "'Standard Currency'" in sql


def test_seeds_expected_units_of_measure():
    sql = _sql_text()
    for code in ["KG", "TON", "L", "EA"]:
        assert re.search(rf"'{code}'", sql), f"Expected unit code {code} to be seeded"


def test_seeds_cityscape_as_primary_active_city():
    sql = _sql_text()
    assert "'CityScape'" in sql
    assert "IsPrimaryActive" in sql


def test_seeds_cinis_baseline_scenario():
    sql = _sql_text()
    assert "'Cinis'" in sql
    assert "'Cinis Baseline'" in sql
