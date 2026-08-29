"""Unit tests for the migration runner's pure logic (no live database needed)."""

from pathlib import Path

import pytest

from cinis.database.migration_runner import discover_migrations, split_batches


def test_discover_migrations_sorts_by_filename(tmp_path: Path):
    (tmp_path / "0002_add_world_table.sql").write_text("SELECT 1;")
    (tmp_path / "0001_create_migration_history.sql").write_text("SELECT 1;")
    (tmp_path / "0010_add_city_table.sql").write_text("SELECT 1;")
    (tmp_path / "notes.txt").write_text("not a migration")

    migrations = discover_migrations(tmp_path)
    names = [m.name for m in migrations]

    assert names == [
        "0001_create_migration_history.sql",
        "0002_add_world_table.sql",
        "0010_add_city_table.sql",
    ]


def test_discover_migrations_missing_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        discover_migrations(tmp_path / "does_not_exist")


def test_split_batches_splits_on_bare_go_lines():
    sql = """
    CREATE TABLE dbo.Foo (Id INT);
    GO
    INSERT INTO dbo.Foo (Id) VALUES (1);
    GO
    """
    batches = split_batches(sql)

    assert len(batches) == 2
    assert "CREATE TABLE dbo.Foo" in batches[0]
    assert "INSERT INTO dbo.Foo" in batches[1]


def test_split_batches_ignores_go_inside_a_string_is_not_supported_but_bare_go_works():
    # Documents current behavior: only a line containing solely "GO" (optionally
    # padded with whitespace) is treated as a batch separator.
    sql = "SELECT 'GO team' AS Message;\nGO\nSELECT 2;"
    batches = split_batches(sql)

    assert len(batches) == 2
    assert "GO team" in batches[0]
    assert "SELECT 2" in batches[1]


def test_split_batches_with_no_go_returns_single_batch():
    sql = "SELECT 1;"
    batches = split_batches(sql)

    assert batches == ["SELECT 1;"]


def test_split_batches_ignores_trailing_blank_batches():
    sql = "SELECT 1;\nGO\n\n"
    batches = split_batches(sql)

    assert batches == ["SELECT 1;"]
