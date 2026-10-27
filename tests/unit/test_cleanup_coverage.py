"""
M5 Step 5.1: static check that the integration-test cleanup
(tests/integration/conftest.py::_cleanup_test_rows) covers the schema.

Why this exists: the session-end cleanup runs as one transaction and
swallows pyodbc.Error, so a single FK-order mistake silently leaves EVERY
Test row behind with no message. That has bitten three times already (the
conftest gaps found in M4 Steps 4.4c-4.7, and the Market tables found
before M5's first committed Market rows). This test derives the FK graph
from the migration files and checks, with no database, that:

  1. every table that references a table the cleanup deletes from is
     itself deleted by the cleanup (so a new domain table that FKs to
     City/Scenario/etc. cannot be forgotten), and
  2. every such child is deleted BEFORE its parent.

Rule 1 is deliberately strict. If a future table references a cleaned
table but tests never leave committed rows in it, add it to
KNOWN_UNPOPULATED_BY_TESTS below with a reason - a conscious decision
rather than a silent omission.

The checkers are pure functions so they can be tested against synthetic
graphs (negative cases), proving the check itself would catch a gap.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
CONFTEST = REPO_ROOT / "tests" / "integration" / "conftest.py"

# Tables that reference a cleaned table but are never populated by tests
# with committed rows. Empty today; every entry needs a reason.
KNOWN_UNPOPULATED_BY_TESTS: dict[str, str] = {}

_TOKEN = re.compile(
    r"(CREATE\s+TABLE|ALTER\s+TABLE)\s+dbo\.(\w+)|REFERENCES\s+dbo\.(\w+)",
    re.IGNORECASE,
)


def parse_foreign_key_edges(sql_texts: list[str]) -> set[tuple[str, str]]:
    """Return {(child_table, parent_table)} for every FK in the given
    migration texts. Self-references are ignored. SQL comments are
    stripped first so commented-out DDL is not counted."""
    edges: set[tuple[str, str]] = set()
    for text in sql_texts:
        text = re.sub(r"--[^\n]*", "", text)
        current: str | None = None
        for match in _TOKEN.finditer(text):
            if match.group(2):
                current = match.group(2)
            elif current and current != match.group(3):
                edges.add((current, match.group(3)))
    return edges


def parse_delete_order(conftest_text: str) -> list[str]:
    """Tables deleted by _cleanup_test_rows, in order of first DELETE."""
    body = re.search(r"^def _cleanup_test_rows.*?(?=^\S)", conftest_text, re.S | re.M)
    assert body, "_cleanup_test_rows not found in tests/integration/conftest.py"
    order: list[str] = []
    for match in re.finditer(r"DELETE FROM dbo\.(\w+)", body.group(0)):
        if match.group(1) not in order:
            order.append(match.group(1))
    return order


def find_uncovered_children(
    edges: set[tuple[str, str]], delete_order: list[str], allowed: dict[str, str]
) -> list[tuple[str, str]]:
    """(child, parent) pairs where parent is cleaned but child is neither
    cleaned nor explicitly allowed."""
    cleaned = set(delete_order)
    return sorted(
        (child, parent)
        for child, parent in edges
        if parent in cleaned and child not in cleaned and child not in allowed
    )


def find_order_violations(
    edges: set[tuple[str, str]], delete_order: list[str]
) -> list[tuple[str, str]]:
    """(child, parent) pairs where the child is deleted after its parent."""
    position = {table: i for i, table in enumerate(delete_order)}
    return sorted(
        (child, parent)
        for child, parent in edges
        if child in position and parent in position and position[child] > position[parent]
    )


# --- The real schema and the real cleanup ---------------------------------


def _real_edges() -> set[tuple[str, str]]:
    texts = [p.read_text(encoding="utf-8-sig") for p in sorted(MIGRATIONS_DIR.glob("*.sql"))]
    return parse_foreign_key_edges(texts)


def _real_delete_order() -> list[str]:
    return parse_delete_order(CONFTEST.read_text(encoding="utf-8"))


def test_cleanup_covers_every_table_that_references_a_cleaned_table():
    uncovered = find_uncovered_children(_real_edges(), _real_delete_order(), KNOWN_UNPOPULATED_BY_TESTS)
    assert not uncovered, (
        "Tables reference a cleaned table but are not deleted by _cleanup_test_rows "
        f"(child, parent): {uncovered}. Add a DELETE before the parent's, or add the "
        "child to KNOWN_UNPOPULATED_BY_TESTS with a reason."
    )


def test_cleanup_deletes_children_before_parents():
    violations = find_order_violations(_real_edges(), _real_delete_order())
    assert not violations, f"Deleted after their parent (child, parent): {violations}"


def test_parser_finds_the_edges_and_deletes_the_checks_depend_on():
    # Guards against the parser silently degrading so the two checks above
    # pass vacuously.
    edges = _real_edges()
    for expected in (
        ("Market", "City"),
        ("MarketTransaction", "Market"),
        ("MarketResourcePrice", "Scenario"),
        ("TreasuryLedgerEntry", "Treasury"),
        ("Treasury", "City"),
        ("SimulationRun", "Scenario"),
    ):
        assert expected in edges, f"FK edge {expected} not parsed from migrations"

    order = _real_delete_order()
    for table in ("Market", "MarketTransaction", "MarketResourcePrice", "TreasuryLedgerEntry"):
        assert table in order, f"{table} is not deleted by _cleanup_test_rows"


# --- The checkers themselves, against synthetic graphs ---------------------


def test_checker_flags_a_child_table_missing_from_the_cleanup():
    # The Market gap, reproduced: Market references City but is not cleaned.
    edges = {("Market", "City"), ("Treasury", "City")}
    assert find_uncovered_children(edges, ["Treasury", "City"], {}) == [("Market", "City")]


def test_checker_accepts_an_explicitly_allowed_child():
    edges = {("Market", "City")}
    assert find_uncovered_children(edges, ["City"], {"Market": "tests never populate it"}) == []


def test_checker_flags_a_child_deleted_after_its_parent():
    edges = {("Market", "City")}
    assert find_order_violations(edges, ["City", "Market"]) == [("Market", "City")]
    assert find_order_violations(edges, ["Market", "City"]) == []


def test_parser_ignores_self_references_and_comments():
    sql = """
    -- CREATE TABLE dbo.Ghost (X INT, FOREIGN KEY (X) REFERENCES dbo.City (CityID));
    CREATE TABLE dbo.Scenario (
        ScenarioID INT, ParentScenarioID INT,
        CONSTRAINT FK_P FOREIGN KEY (ParentScenarioID) REFERENCES dbo.Scenario (ScenarioID),
        CONSTRAINT FK_S FOREIGN KEY (SimulationID) REFERENCES dbo.Simulation (SimulationID)
    );
    ALTER TABLE dbo.Widget ADD CONSTRAINT FK_W FOREIGN KEY (CityID) REFERENCES dbo.City (CityID);
    """
    assert parse_foreign_key_edges([sql]) == {("Scenario", "Simulation"), ("Widget", "City")}
