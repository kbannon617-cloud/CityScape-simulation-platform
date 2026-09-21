"""
Integration tests for the NeedTypeResource table (migrations 0021/0022)
against real SQL Server.

Constraint tests run in an uncommitted raw transaction that is rolled back
in a finally block, so real seeded data is never changed.
"""

from __future__ import annotations

import pyodbc
import pytest

# The mapping approved in ADR-0010 Decision 2. Checked as a subset (not
# equality) so later data changes, such as adding rows while balancing, do
# not break this test.
EXPECTED_SEEDED_MAPPING = {
    ("FOOD", "R-001", 1),  # Wheat
    ("FOOD", "R-002", 2),  # Trout
    ("FOOD", "R-009", 3),  # Eggs
    ("FOOD", "R-010", 4),  # Lentils
    ("HEATING", "R-004", 1),  # Timber
}

INSERT_SQL = (
    "INSERT INTO dbo.NeedTypeResource (NeedTypeID, ResourceID, ConsumptionPriority) "
    "SELECT nt.NeedTypeID, r.ResourceID, ? "
    "FROM dbo.NeedType nt, dbo.Resource r WHERE nt.Code = ? AND r.Code = ?"
)


def test_table_constraints_and_foreign_keys_exist(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'NeedTypeResource'")
    assert cursor.fetchone()[0] == 1

    cursor.execute(
        "SELECT name FROM sys.key_constraints "
        "WHERE parent_object_id = OBJECT_ID('dbo.NeedTypeResource') AND type = 'UQ'"
    )
    assert {row[0] for row in cursor.fetchall()} == {
        "UQ_NeedTypeResource_NeedType_Resource",
        "UQ_NeedTypeResource_NeedType_Priority",
    }

    cursor.execute(
        "SELECT name FROM sys.check_constraints "
        "WHERE parent_object_id = OBJECT_ID('dbo.NeedTypeResource')"
    )
    assert {row[0] for row in cursor.fetchall()} == {
        "CK_NeedTypeResource_ConsumptionPriority_Positive"
    }

    cursor.execute(
        "SELECT name FROM sys.foreign_keys "
        "WHERE parent_object_id = OBJECT_ID('dbo.NeedTypeResource')"
    )
    assert {row[0] for row in cursor.fetchall()} == {
        "FK_NeedTypeResource_NeedType",
        "FK_NeedTypeResource_Resource",
    }
    connection.rollback()


def test_seeded_mapping_is_present(connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT nt.Code, r.Code, ntr.ConsumptionPriority "
        "FROM dbo.NeedTypeResource ntr "
        "JOIN dbo.NeedType nt ON nt.NeedTypeID = ntr.NeedTypeID "
        "JOIN dbo.Resource r ON r.ResourceID = ntr.ResourceID"
    )
    rows = {tuple(row) for row in cursor.fetchall()}
    connection.rollback()

    assert EXPECTED_SEEDED_MAPPING <= rows


def test_seeded_priorities_read_back_in_consumption_order(connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT r.Code FROM dbo.NeedTypeResource ntr "
        "JOIN dbo.NeedType nt ON nt.NeedTypeID = ntr.NeedTypeID "
        "JOIN dbo.Resource r ON r.ResourceID = ntr.ResourceID "
        "WHERE nt.Code = 'FOOD' AND ntr.ConsumptionPriority <= 4 "
        "ORDER BY ntr.ConsumptionPriority"
    )
    order = [row[0] for row in cursor.fetchall()]
    connection.rollback()

    assert order == ["R-001", "R-002", "R-009", "R-010"]


def test_an_unused_resource_can_be_mapped_at_a_free_priority(connection):
    """Control case: proves the rejections below come from the specific
    constraints, not from a problem with the test's own INSERT."""
    cursor = connection.cursor()
    try:
        cursor.execute(INSERT_SQL, 99, "FOOD", "R-011")  # Ore at priority 99
        assert cursor.rowcount == 1
    finally:
        connection.rollback()


@pytest.mark.parametrize(
    "priority, need_code, resource_code, reason",
    [
        (99, "FOOD", "R-001", "the same resource twice for one need type"),
        (1, "FOOD", "R-011", "a priority already used within the need type"),
        (0, "FOOD", "R-011", "a priority below 1"),
        (-1, "FOOD", "R-011", "a negative priority"),
    ],
)
def test_database_rejects_invalid_mappings(
    connection, priority, need_code, resource_code, reason
):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            cursor.execute(INSERT_SQL, priority, need_code, resource_code)
    finally:
        connection.rollback()


def test_database_rejects_nonexistent_need_type_and_resource(connection):
    cursor = connection.cursor()
    try:
        with pytest.raises(pyodbc.Error):
            cursor.execute(
                "INSERT INTO dbo.NeedTypeResource (NeedTypeID, ResourceID, ConsumptionPriority) "
                "VALUES (-1, -1, 50)"
            )
    finally:
        connection.rollback()
