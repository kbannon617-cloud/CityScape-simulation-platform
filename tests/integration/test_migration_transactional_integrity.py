"""
Integration test proving the migration runner's transactional guarantee:
if any batch in a migration fails, none of that migration's earlier batches
remain committed. This is the M1-level equivalent of Document 7's "no
partial persistence after failed ticks" invariant, applied to migrations
since ticks don't exist yet.
"""

from __future__ import annotations

from pathlib import Path

import pyodbc
import pytest

from cinis.database.migration_runner import Migration, apply_migration


@pytest.fixture
def broken_migration_table_name():
    # Unique-enough per test session; cleaned up by this test itself.
    return "TestRollbackProof"


def test_failed_migration_batch_rolls_back_completely(
    connection, tmp_path: Path, broken_migration_table_name: str
):
    table = broken_migration_table_name
    cursor = connection.cursor()

    # Defensive cleanup in case a previous failed test run left this behind.
    cursor.execute(
        "IF EXISTS (SELECT 1 FROM sys.tables WHERE name = ?) "
        f"DROP TABLE dbo.{table}",
        table,
    )
    connection.commit()

    # Batch 1 succeeds (creates a real table). Batch 2 is deliberately
    # broken (references a column that does not exist). If the runner's
    # transaction handling works, batch 1's table must NOT exist afterward.
    migration_sql = f"""
    CREATE TABLE dbo.{table} (Id INT);
    GO
    INSERT INTO dbo.{table} (NoSuchColumn) VALUES (1);
    GO
    """
    migration_file = tmp_path / "9999_deliberately_broken.sql"
    migration_file.write_text(migration_sql, encoding="utf-8")
    migration = Migration(name=migration_file.name, path=migration_file)

    with pytest.raises(pyodbc.Error):
        apply_migration(connection, migration)

    cursor.execute("SELECT 1 FROM sys.tables WHERE name = ?", table)
    row = cursor.fetchone()
    assert row is None, (
        "Batch 1 (CREATE TABLE) must not remain committed after batch 2 "
        "failed - partial persistence would violate the no-partial-commit "
        "guarantee."
    )

    # Also confirm MigrationHistory was never told this migration applied.
    cursor.execute(
        "SELECT 1 FROM dbo.MigrationHistory WHERE ScriptName = ?",
        migration.name,
    )
    assert cursor.fetchone() is None
