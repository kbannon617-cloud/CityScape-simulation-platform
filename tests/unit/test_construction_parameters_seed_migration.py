"""Unit tests for the 0024 construction ScenarioParameter seed migration file (no database needed)."""

from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0024_seed_construction_parameters.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_seeds_the_three_approved_parameters_with_workbook_values():
    sql = _sql_text()
    assert "'MonthlyConstructionBudget', 100.0" in sql
    assert "'ConstructionBonusPerCompletedCrew', 0.0005" in sql
    assert "'MaxActiveConstructionProjectsPerCity', 1" in sql


def test_targets_the_cinis_baseline_scenario():
    sql = _sql_text()
    assert "s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'" in sql


def test_every_insert_is_guarded_for_safe_rerun():
    sql = _sql_text()
    assert sql.count("IF NOT EXISTS (") == 3


def test_is_additive_only():
    sql = _sql_text().upper()
    for forbidden in ("DROP ", "UPDATE ", "DELETE ", "ALTER ", "TRUNCATE", "CREATE TABLE"):
        assert forbidden not in sql
