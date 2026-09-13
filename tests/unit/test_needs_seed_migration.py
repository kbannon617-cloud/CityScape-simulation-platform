"""Unit tests for the 0008 needs and labor seed data migration file."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0008_seed_needs_and_labor_data.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_seeds_all_three_need_categories():
    sql = _sql_text()
    for code in ["FOOD", "HEATING", "BASIC_GOODS"]:
        assert f"'{code}'" in sql


def test_seeds_consumption_rates_for_both_group_types():
    sql = _sql_text()
    assert "@AdultTypeID" in sql
    assert "@ChildTypeID" in sql


def test_seeds_labor_participation_rate_as_scenario_parameter():
    sql = _sql_text()
    assert "AdultLaborParticipationRatePercent" in sql
    assert "INSERT INTO dbo.ScenarioParameter" in sql
