"""Unit tests for the 0020 ledger run/tick columns migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0020_add_ledger_run_and_tick_columns.sql"
)

TABLES = ("InventoryLedgerEntry", "TreasuryLedgerEntry")


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _code_only() -> str:
    """The SQL with comment lines removed, so keyword checks ignore prose."""
    return "\n".join(
        line for line in _sql_text().splitlines() if not line.strip().startswith("--")
    )


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_splits_into_two_batches():
    """Columns first, then the CHECKs that reference them."""
    assert len(split_batches(_sql_text())) == 2


def test_columns_are_added_to_both_ledger_tables():
    code = _code_only()
    for table in TABLES:
        assert re.search(rf"ALTER TABLE dbo\.{table} ADD\s+SimulationRunID\s+INT\s+NULL", code)
        assert re.search(r"SimulationTickID\s+BIGINT\s+NULL", code)


def test_columns_are_added_in_the_first_batch_and_checks_in_the_second():
    first, second = split_batches(_sql_text())
    assert "SimulationRunID  INT    NULL" in first
    assert "ADD CONSTRAINT" not in first
    assert "ADD CONSTRAINT CK_" in second
    assert "ADD\n        SimulationRunID" not in second


def test_run_column_has_foreign_key_to_simulation_run():
    code = _code_only()
    assert "FK_InventoryLedgerEntry_SimulationRun REFERENCES dbo.SimulationRun (SimulationRunID)" in code
    assert "FK_TreasuryLedgerEntry_SimulationRun REFERENCES dbo.SimulationRun (SimulationRunID)" in code


def test_both_or_neither_check_exists_on_both_tables():
    code = _code_only()
    for table in TABLES:
        assert f"CK_{table}_Trace_BothOrNeither" in code
    assert code.count("SimulationRunID IS NULL AND SimulationTickID IS NULL") == 2
    assert code.count("SimulationRunID IS NOT NULL AND SimulationTickID IS NOT NULL") == 2


def test_tick_must_be_positive_when_present_on_both_tables():
    code = _code_only()
    for table in TABLES:
        assert f"CK_{table}_SimulationTickID_Positive" in code
    assert code.count("CHECK (SimulationTickID IS NULL OR SimulationTickID >= 1)") == 2


def test_every_step_is_guarded_for_safe_rerun():
    code = _code_only()
    assert code.count("COL_LENGTH(") == 2
    assert code.count("IF NOT EXISTS (SELECT 1 FROM sys.check_constraints") == 4


def test_migration_is_additive_only():
    code = _code_only().upper()
    for forbidden in ("DROP ", "UPDATE ", "DELETE ", "ALTER COLUMN", "TRUNCATE", "CREATE TABLE"):
        assert forbidden not in code
