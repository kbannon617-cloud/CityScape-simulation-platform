"""
Migration runner for the Cinis SQL Server database.

Migrations are plain, numbered .sql files under database/migrations/,
applied strictly in ascending filename order. Each applied script is
recorded in dbo.MigrationHistory so re-running the tool is safe.

SSMS-style scripts commonly separate batches with a bare "GO" line; that
is a client-side directive, not valid T-SQL, so we split on it before
sending each batch to pyodbc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pyodbc

GO_SPLIT_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Migration:
    name: str
    path: Path

    @property
    def sort_key(self) -> str:
        return self.name


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    """Return all .sql migrations in migrations_dir, sorted by filename."""
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")

    migrations = [
        Migration(name=p.name, path=p)
        for p in migrations_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".sql"
    ]
    return sorted(migrations, key=lambda m: m.sort_key)


def split_batches(sql_text: str) -> list[str]:
    """Split a SQL script on bare 'GO' lines into individually-executable batches."""
    batches = GO_SPLIT_RE.split(sql_text)
    return [b.strip() for b in batches if b.strip()]


def get_applied_migrations(cursor: pyodbc.Cursor) -> set[str]:
    """Return the set of script names already recorded as applied.

    Returns an empty set if MigrationHistory does not exist yet (i.e.
    no migration, including 0001, has ever been applied).
    """
    cursor.execute("SELECT 1 FROM sys.tables WHERE name = 'MigrationHistory'")
    if cursor.fetchone() is None:
        return set()

    cursor.execute("SELECT ScriptName FROM dbo.MigrationHistory")
    return {row[0] for row in cursor.fetchall()}


def apply_migration(connection: pyodbc.Connection, migration: Migration) -> None:
    """Apply a single migration's batches and record it, in one transaction."""
    sql_text = migration.path.read_text(encoding="utf-8")
    batches = split_batches(sql_text)

    cursor = connection.cursor()
    try:
        for batch in batches:
            cursor.execute(batch)
        cursor.execute(
            "INSERT INTO dbo.MigrationHistory (ScriptName) VALUES (?)",
            migration.name,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def run_pending_migrations(
    connection: pyodbc.Connection, migrations_dir: Path
) -> list[str]:
    """Apply all not-yet-applied migrations in order. Returns names applied."""
    cursor = connection.cursor()
    applied_already = get_applied_migrations(cursor)

    all_migrations = discover_migrations(migrations_dir)
    pending = [m for m in all_migrations if m.name not in applied_already]

    applied_now: list[str] = []
    for migration in pending:
        apply_migration(connection, migration)
        applied_now.append(migration.name)

    return applied_now
