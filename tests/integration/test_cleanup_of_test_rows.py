"""
M5 Step 5.1: proves the integration-test cleanup actually EXECUTES against
real SQL Server and removes what M5's vertical slice will leave behind -
the Market family (Market, MarketResourcePrice, MarketTransaction) and an
untraced TreasuryLedgerEntry on a Test city's Treasury.

The static test (tests/unit/test_cleanup_coverage.py) checks coverage and
order from the migrations; this one catches what static analysis cannot - a
mistyped column or table name inside a cleanup statement. That matters
because the session-end cleanup swallows pyodbc.Error: one bad statement
there would silently skip the whole cleanup.

It also covers the shape that was found silently blocking the cleanup in
this step: a Scenario WITHOUT the Test prefix owned by a Test-named
Simulation, with children of its own (ScenarioParameter, SimulationRun).
The earliest M1 tests produced exactly that, and the name-only Scenario
match skipped them - see the OWNERSHIP RULE in conftest.py.

Safe by construction, and stronger than the SAVEPOINT pattern: everything
(insert, cleanup, assertions) happens inside ONE uncommitted transaction on
the session's pyodbc connection, and the test always rolls back in its
finally block. Nothing is ever committed, so even if the cleanup under test
is broken this cannot leave rows in the development database. (The cleanup
deletes every "Test%" row visible to this transaction, including rows other
tests committed earlier; the rollback restores those too.)
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal


def _insert_returning_id(cursor, sql, *params) -> int:
    cursor.execute(sql, *params)
    return cursor.fetchone()[0]


def _scalar(cursor, sql, *params):
    cursor.execute(sql, *params)
    return cursor.fetchone()[0]


def test_cleanup_removes_market_family_and_untraced_treasury_rows(connection, cleanup_test_rows):
    suffix = uuid.uuid4().hex[:8]
    cursor = connection.cursor()
    try:
        world_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)",
            f"TestWorldCleanup-{suffix}",
        )
        region_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
            world_id, f"TestRegionCleanup-{suffix}",
        )
        city_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) "
            "OUTPUT INSERTED.CityID VALUES (?, ?, 0)",
            region_id, f"TestCityCleanup-{suffix}",
        )
        simulation_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Simulation (Name) OUTPUT INSERTED.SimulationID VALUES (?)",
            f"TestSimulationCleanup-{suffix}",
        )
        scenario_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Scenario (SimulationID, Name) OUTPUT INSERTED.ScenarioID VALUES (?, ?)",
            simulation_id, f"TestScenarioCleanup-{suffix}",
        )

        # The legacy shape: no Test prefix on the Scenario, but owned by a
        # Test-named Simulation, with children keyed to it.
        legacy_scenario_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Scenario (SimulationID, Name) OUTPUT INSERTED.ScenarioID VALUES (?, ?)",
            simulation_id, f"LegacyStyleScenario-{suffix}",
        )
        cursor.execute(
            "INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue) VALUES (?, ?, ?)",
            legacy_scenario_id, "CleanupProbeKey", Decimal("1.000000"),
        )
        cursor.execute(
            "INSERT INTO dbo.SimulationRun (ScenarioID, StartSimulationDate, CurrentSimulationDate) "
            "VALUES (?, ?, ?)",
            legacy_scenario_id, datetime.date(1880, 1, 31), datetime.date(1880, 1, 31),
        )

        # Real seeded reference rows (migrations 0003, 0010, 0012).
        currency_id = _scalar(cursor, "SELECT CurrencyID FROM dbo.Currency WHERE Code = 'STD'")
        resource_id = _scalar(cursor, "SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
        category_id = _scalar(
            cursor, "SELECT TOP 1 TreasuryCategoryTypeID FROM dbo.TreasuryCategoryType ORDER BY TreasuryCategoryTypeID"
        )

        treasury_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Treasury (CityID, CurrencyID, Balance) "
            "OUTPUT INSERTED.TreasuryID VALUES (?, ?, ?)",
            city_id, currency_id, Decimal("100.00"),
        )
        # Untraced: SimulationRunID/SimulationTickID left NULL, as for any
        # command issued outside a tick. The old run-only cleanup missed
        # these, and they would have blocked the Treasury delete.
        cursor.execute(
            "INSERT INTO dbo.TreasuryLedgerEntry (TreasuryID, TreasuryCategoryTypeID, EntryDate, Amount) "
            "VALUES (?, ?, ?, ?)",
            treasury_id, category_id, datetime.date(1880, 2, 1), Decimal("5.00"),
        )

        market_id = _insert_returning_id(
            cursor,
            "INSERT INTO dbo.Market (CityID) OUTPUT INSERTED.MarketID VALUES (?)",
            city_id,
        )
        cursor.execute(
            "INSERT INTO dbo.MarketResourcePrice (ScenarioID, ResourceID, CurrencyID, UnitPrice) "
            "VALUES (?, ?, ?, ?)",
            scenario_id, resource_id, currency_id, Decimal("2.0000"),
        )
        cursor.execute(
            "INSERT INTO dbo.MarketTransaction "
            "(MarketID, ResourceID, TransactionType, Quantity, UnitPrice, TotalValue, TransactionDate) "
            "VALUES (?, ?, 'Buy', ?, ?, ?, ?)",
            market_id, resource_id, Decimal("1.0000"), Decimal("2.0000"), Decimal("2.0000"),
            datetime.date(1880, 2, 1),
        )

        # Pre-condition: the rows exist, so "0 afterwards" proves something.
        probes = {
            "City": ("SELECT COUNT(*) FROM dbo.City WHERE CityID = ?", city_id),
            "Simulation": ("SELECT COUNT(*) FROM dbo.Simulation WHERE SimulationID = ?", simulation_id),
            "Scenario": ("SELECT COUNT(*) FROM dbo.Scenario WHERE ScenarioID = ?", scenario_id),
            "Scenario (no Test prefix, owned by Test Simulation)": (
                "SELECT COUNT(*) FROM dbo.Scenario WHERE ScenarioID = ?",
                legacy_scenario_id,
            ),
            "ScenarioParameter (under non-Test Scenario)": (
                "SELECT COUNT(*) FROM dbo.ScenarioParameter WHERE ScenarioID = ?",
                legacy_scenario_id,
            ),
            "SimulationRun (under non-Test Scenario)": (
                "SELECT COUNT(*) FROM dbo.SimulationRun WHERE ScenarioID = ?",
                legacy_scenario_id,
            ),
            "Treasury": ("SELECT COUNT(*) FROM dbo.Treasury WHERE TreasuryID = ?", treasury_id),
            "TreasuryLedgerEntry (untraced)": (
                "SELECT COUNT(*) FROM dbo.TreasuryLedgerEntry "
                "WHERE TreasuryID = ? AND SimulationRunID IS NULL",
                treasury_id,
            ),
            "Market": ("SELECT COUNT(*) FROM dbo.Market WHERE MarketID = ?", market_id),
            "MarketResourcePrice": (
                "SELECT COUNT(*) FROM dbo.MarketResourcePrice WHERE ScenarioID = ?",
                scenario_id,
            ),
            "MarketTransaction": (
                "SELECT COUNT(*) FROM dbo.MarketTransaction WHERE MarketID = ?",
                market_id,
            ),
        }
        before = {name: _scalar(cursor, sql, param) for name, (sql, param) in probes.items()}
        assert before == {name: 1 for name in probes}, f"setup did not create every row: {before}"

        # The code under test. Raises pyodbc.Error on any bad statement or
        # FK-order mistake - exactly the failure the session-end cleanup
        # would otherwise swallow.
        cleanup_test_rows(cursor)

        after = {name: _scalar(cursor, sql, param) for name, (sql, param) in probes.items()}
        assert after == {name: 0 for name in probes}, f"cleanup left rows behind: {after}"
    finally:
        connection.rollback()
