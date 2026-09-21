"""Unit tests for the 0022 NeedTypeResource seed migration file (no database needed)."""

import re
from pathlib import Path

from cinis.database.migration_runner import split_batches

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "0022_seed_need_type_resource.sql"
)


def _sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _code_only() -> str:
    return "\n".join(
        line for line in _sql_text().splitlines() if not line.strip().startswith("--")
    )


def _seeded_rows() -> list[tuple[str, str, int]]:
    return [
        (need, resource, int(priority))
        for need, resource, priority in re.findall(
            r"\(\s*'([A-Z_]+)'\s*,\s*'(R-\d+)'\s*,\s*(\d+)\s*\)", _code_only()
        )
    ]


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_a_single_batch():
    assert len(split_batches(_sql_text())) == 1


def test_seeds_the_approved_mapping_exactly():
    assert _seeded_rows() == [
        ("FOOD", "R-001", 1),  # Wheat
        ("FOOD", "R-002", 2),  # Trout
        ("FOOD", "R-009", 3),  # Eggs
        ("FOOD", "R-010", 4),  # Lentils
        ("HEATING", "R-004", 1),  # Timber
    ]


def test_basic_goods_is_deliberately_unmapped():
    assert "'BASIC_GOODS'" not in _code_only()


def test_priorities_are_unique_within_each_need_type():
    seen = set()
    for need, _, priority in _seeded_rows():
        assert (need, priority) not in seen
        seen.add((need, priority))


def test_insert_is_guarded_for_safe_rerun():
    assert "WHERE NOT EXISTS" in _code_only()


def test_is_additive_only():
    code = _code_only().upper()
    for forbidden in ("DROP ", "UPDATE ", "DELETE ", "ALTER ", "TRUNCATE", "CREATE TABLE"):
        assert forbidden not in code
