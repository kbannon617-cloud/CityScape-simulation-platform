"""
Run pending Cinis database migrations.

Usage:
    python scripts/run_migrations.py

Reads connection settings from environment variables (see .env.example).
Applies every not-yet-applied script under database/migrations/, in order,
and prints what was applied.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyodbc

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cinis.config.dotenv import load_dotenv  # noqa: E402
from cinis.config.settings import ConfigurationError, load_database_settings  # noqa: E402
from cinis.database.migration_runner import run_pending_migrations  # noqa: E402

MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")

    try:
        settings = load_database_settings()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    # pyodbc connection string built directly (kept independent of the
    # SQLAlchemy URL used elsewhere, since pyodbc.connect() wants its own format).
    if settings.auth_mode == "windows":
        conn_str = (
            f"DRIVER={{{settings.driver}}};SERVER={settings.server};"
            f"DATABASE={settings.database};Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{settings.driver}}};SERVER={settings.server};"
            f"DATABASE={settings.database};UID={settings.user};PWD={settings.password};"
        )

    try:
        connection = pyodbc.connect(conn_str)
    except pyodbc.Error as exc:
        print(f"Could not connect to database: {exc}", file=sys.stderr)
        return 1

    try:
        applied = run_pending_migrations(connection, MIGRATIONS_DIR)
    finally:
        connection.close()

    if not applied:
        print("No pending migrations. Database is up to date.")
    else:
        print(f"Applied {len(applied)} migration(s):")
        for name in applied:
            print(f"  - {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
