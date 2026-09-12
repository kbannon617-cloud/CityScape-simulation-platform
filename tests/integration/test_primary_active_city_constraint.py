"""
Integration test proving the 0004 filtered unique index actually enforces
"exactly one primary active city" at the database level, not just in
application code. This is the concrete verification for the Option A
decision recorded in ADR-0003 / the follow-up bug in ADR-0004.
"""

from __future__ import annotations

import uuid

import pyodbc
import pytest


def test_second_primary_active_city_is_rejected_by_the_database(connection):
    cursor = connection.cursor()
    suffix = uuid.uuid4().hex[:8]

    cursor.execute(
        "INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)",
        f"TestWorld-{suffix}",
    )
    world_id = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
        world_id,
        f"TestRegion-{suffix}",
    )
    region_id = cursor.fetchone()[0]
    connection.commit()

    # The real seeded CityScape is already IsPrimaryActive = 1. A second
    # row with IsPrimaryActive = 1 must be rejected by the unique index,
    # regardless of what application code does or doesn't check.
    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) VALUES (?, ?, ?)",
            region_id,
            f"TestSecondPrimaryCity-{suffix}",
            1,
        )
        connection.commit()
    connection.rollback()

    # A non-primary-active test city must still be allowed (the index is
    # filtered, not a blanket uniqueness constraint on the whole column).
    cursor.execute(
        "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) VALUES (?, ?, ?)",
        region_id,
        f"TestNonPrimaryCity-{suffix}",
        0,
    )
    connection.commit()

    cursor.execute("SELECT COUNT(*) FROM dbo.City WHERE IsPrimaryActive = 1")
    assert cursor.fetchone()[0] == 1, "Exactly one primary active city must exist"
