"""Unit tests for the 0006 population seed data migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0006_seed_population_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_three_batches():
    batches = split_batches(_sql_text())
    assert len(batches) == 3


def test_seeds_adult_and_child_group_types():
    sql = _sql_text()
    assert "'ADULT'" in sql
    assert "'CHILD'" in sql


def test_seeds_placeholder_starting_counts():
    sql = _sql_text()
    assert "100" in sql  # placeholder Adult count
    assert "20" in sql  # placeholder Child count


def test_seeds_aging_rate_as_scenario_parameter_not_hardcoded():
    sql = _sql_text()
    assert "ChildToAdultMonthlyAgingRatePercent" in sql
    assert "INSERT INTO dbo.ScenarioParameter" in sql
