"""
M5 Step 5.2: smoke tests for tests/integration/isolated_city.py.

The vertical-slice tests (Steps 5.3 and 5.4) trust this builder completely,
so it is verified on its own first: if a slice assertion later fails, the
cause is the engine or services, not the setup. Every check reads state
back through raw SQL, independently of the ORM/service code the builder
used to write it.

The final test fingerprints the real CityScape city before and after a
build and requires them to be identical - the executable form of the M5
decision that the real city stays untouched.
"""

from __future__ import annotations

import dataclasses
import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cinis.config.settings import load_database_settings
from isolated_city import (
    DEFAULT_BUILDINGS,
    DEFAULT_OPENING_STOCK,
    DEFAULT_RESOURCE_PRICES,
    DEFAULT_SCENARIO_PARAMETERS,
    SLICE_START_DATE,
    build_isolated_city,
)


@pytest.fixture(scope="module")
def session_factory(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    yield sessionmaker(bind=engine)
    engine.dispose()


def _rows(session_factory, sql, *params):
    """Run a read-only query; return rows as plain tuples (pyodbc.Row does
    not reliably support == against a tuple, so never compare Rows)."""
    session = session_factory()
    try:
        cursor = session.connection().connection.cursor()
        cursor.execute(sql, *params)
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        session.rollback()
        session.close()


def _scalar(session_factory, sql, *params):
    return _rows(session_factory, sql, *params)[0][0]


def _real_city_fingerprint(session_factory) -> dict:
    """Everything about the real primary-active city that a slice test
    could plausibly disturb. Read-only."""
    primary = _rows(session_factory, "SELECT CityID, Name FROM dbo.City WHERE IsPrimaryActive = 1")
    assert len(primary) == 1, f"expected exactly one primary-active city, found {primary}"
    city_id = primary[0][0]
    return {
        "city": primary[0],
        "population": _rows(
            session_factory,
            "SELECT PopulationGroupTypeID, Count FROM dbo.PopulationGroup WHERE CityID = ? "
            "ORDER BY PopulationGroupTypeID",
            city_id,
        ),
        "buildings": _rows(
            session_factory,
            "SELECT BuildingTypeID, Count FROM dbo.Building WHERE CityID = ? ORDER BY BuildingTypeID",
            city_id,
        ),
        "inventory": _rows(
            session_factory,
            "SELECT ResourceID, Quantity FROM dbo.CityInventory WHERE CityID = ? ORDER BY ResourceID",
            city_id,
        ),
        "inventory_ledger_rows": _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.InventoryLedgerEntry le JOIN dbo.CityInventory ci "
            "ON ci.CityInventoryID = le.CityInventoryID WHERE ci.CityID = ?",
            city_id,
        ),
        "treasury": _rows(
            session_factory, "SELECT TreasuryID, Balance FROM dbo.Treasury WHERE CityID = ?", city_id
        ),
        "treasury_ledger_rows": _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.TreasuryLedgerEntry le JOIN dbo.Treasury t "
            "ON t.TreasuryID = le.TreasuryID WHERE t.CityID = ?",
            city_id,
        ),
        "market_transactions": _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.MarketTransaction mt JOIN dbo.Market m "
            "ON m.MarketID = mt.MarketID WHERE m.CityID = ?",
            city_id,
        ),
        "construction_projects": _scalar(
            session_factory, "SELECT COUNT(*) FROM dbo.ConstructionProject WHERE CityID = ?", city_id
        ),
        "snapshots": _scalar(
            session_factory, "SELECT COUNT(*) FROM dbo.CitySnapshot WHERE CityID = ?", city_id
        ),
        "baseline_runs": _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.SimulationRun sr JOIN dbo.Scenario sc "
            "ON sc.ScenarioID = sr.ScenarioID WHERE sc.Name = 'Cinis Baseline'",
        ),
        "baseline_prices": _rows(
            session_factory,
            "SELECT p.ResourceID, p.UnitPrice FROM dbo.MarketResourcePrice p JOIN dbo.Scenario sc "
            "ON sc.ScenarioID = p.ScenarioID WHERE sc.Name = 'Cinis Baseline' ORDER BY p.ResourceID",
        ),
    }


@dataclasses.dataclass(frozen=True)
class Built:
    city: object
    real_before: dict
    real_after: dict


@pytest.fixture(scope="module")
def built(session_factory) -> Built:
    """One default-slice build for the read-only tests, bracketed by real-city
    fingerprints."""
    before = _real_city_fingerprint(session_factory)
    city = build_isolated_city(session_factory)
    after = _real_city_fingerprint(session_factory)
    return Built(city=city, real_before=before, real_after=after)


def test_population_buildings_stock_and_treasury_match_the_slice_defaults(built, session_factory):
    city = built.city

    population = dict(
        _rows(
            session_factory,
            "SELECT t.Code, g.Count FROM dbo.PopulationGroup g JOIN dbo.PopulationGroupType t "
            "ON t.PopulationGroupTypeID = g.PopulationGroupTypeID WHERE g.CityID = ?",
            city.city_id,
        )
    )
    assert population == {"ADULT": 100, "CHILD": 200}

    buildings = dict(
        _rows(
            session_factory,
            "SELECT bt.Code, b.Count FROM dbo.Building b JOIN dbo.BuildingType bt "
            "ON bt.BuildingTypeID = b.BuildingTypeID WHERE b.CityID = ?",
            city.city_id,
        )
    )
    assert buildings == DEFAULT_BUILDINGS

    inventory = dict(
        _rows(
            session_factory,
            "SELECT r.Code, ci.Quantity FROM dbo.CityInventory ci JOIN dbo.Resource r "
            "ON r.ResourceID = ci.ResourceID WHERE ci.CityID = ?",
            city.city_id,
        )
    )
    assert inventory == DEFAULT_OPENING_STOCK
    assert "R-005" not in inventory, "Lumber must not be seeded; only the Saw Mill produces it"

    treasury = _rows(
        session_factory,
        "SELECT Balance FROM dbo.Treasury WHERE TreasuryID = ?",
        city.treasury_id,
    )
    assert treasury == [(Decimal("1000.00"),)]


def test_opening_stock_is_backed_by_untraced_ledger_entries_dated_the_day_before(built, session_factory):
    city = built.city
    rows = _rows(
        session_factory,
        "SELECT ci.CityInventoryID, ci.Quantity, SUM(le.Amount), COUNT(le.InventoryLedgerEntryID), "
        "MIN(le.EntryDate), MAX(le.EntryDate) "
        "FROM dbo.CityInventory ci JOIN dbo.InventoryLedgerEntry le "
        "ON le.CityInventoryID = ci.CityInventoryID WHERE ci.CityID = ? "
        "GROUP BY ci.CityInventoryID, ci.Quantity",
        city.city_id,
    )
    assert len(rows) == len(DEFAULT_OPENING_STOCK)
    expected_date = SLICE_START_DATE - datetime.timedelta(days=1)
    for _inventory_id, quantity, ledger_sum, entries, first, last in rows:
        assert quantity == ledger_sum, "ledger is the source of truth: quantity must equal its sum"
        assert entries == 1
        assert first == last == expected_date

    untraced = _scalar(
        session_factory,
        "SELECT COUNT(*) FROM dbo.InventoryLedgerEntry le JOIN dbo.CityInventory ci "
        "ON ci.CityInventoryID = le.CityInventoryID "
        "WHERE ci.CityID = ? AND (le.SimulationRunID IS NOT NULL OR le.SimulationTickID IS NOT NULL)",
        city.city_id,
    )
    assert untraced == 0, "setup entries are made outside any tick and must carry no trace"


def test_market_and_explicit_prices_exist_for_the_test_scenario_only(built, session_factory):
    city = built.city

    assert _scalar(session_factory, "SELECT COUNT(*) FROM dbo.Market WHERE CityID = ?", city.city_id) == 1
    assert (
        _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.MarketTransaction WHERE MarketID = ?",
            city.market_id,
        )
        == 0
    )

    prices = dict(
        _rows(
            session_factory,
            "SELECT r.Code, p.UnitPrice FROM dbo.MarketResourcePrice p JOIN dbo.Resource r "
            "ON r.ResourceID = p.ResourceID WHERE p.ScenarioID = ?",
            city.scenario_id,
        )
    )
    assert prices == DEFAULT_RESOURCE_PRICES


def test_scenario_parameters_and_run_start_state(built, session_factory):
    city = built.city

    parameters = dict(
        _rows(
            session_factory,
            "SELECT ParameterKey, ParameterValue FROM dbo.ScenarioParameter WHERE ScenarioID = ?",
            city.scenario_id,
        )
    )
    assert set(parameters) == set(DEFAULT_SCENARIO_PARAMETERS)
    for key, expected in DEFAULT_SCENARIO_PARAMETERS.items():
        assert float(parameters[key]) == pytest.approx(expected), key

    run = _rows(
        session_factory,
        "SELECT ScenarioID, StartSimulationDate, CurrentSimulationDate, CurrentSimulationTickID, Status "
        "FROM dbo.SimulationRun WHERE SimulationRunID = ?",
        city.run_id,
    )
    assert run == [(city.scenario_id, SLICE_START_DATE, SLICE_START_DATE, 0, "Active")]


def test_the_city_is_test_named_and_never_primary_active(built, session_factory):
    city = built.city

    names = _rows(
        session_factory,
        "SELECT c.Name, c.IsPrimaryActive, w.Name, rg.Name "
        "FROM dbo.City c JOIN dbo.Region rg ON rg.RegionID = c.RegionID "
        "JOIN dbo.World w ON w.WorldID = rg.WorldID WHERE c.CityID = ?",
        city.city_id,
    )
    assert len(names) == 1
    city_name, is_primary, world_name, region_name = names[0]
    assert not is_primary
    assert city_name.startswith("Test") and world_name.startswith("Test") and region_name.startswith("Test")

    sim_scenario = _rows(
        session_factory,
        "SELECT s.Name, sc.Name FROM dbo.Simulation s JOIN dbo.Scenario sc "
        "ON sc.SimulationID = s.SimulationID WHERE sc.ScenarioID = ?",
        city.scenario_id,
    )
    assert len(sim_scenario) == 1
    assert all(name.startswith("Test") for name in sim_scenario[0])

    primary = _rows(session_factory, "SELECT Name FROM dbo.City WHERE IsPrimaryActive = 1")
    assert primary == [("CityScape",)]


def test_building_the_city_leaves_the_real_cityscape_untouched(built):
    assert built.real_after == built.real_before


def test_overrides_are_respected_and_zero_rows_are_not_seeded(built, session_factory):
    minimal = build_isolated_city(
        session_factory,
        label="Minimal",
        start_date=datetime.date(1880, 3, 31),
        adults=7,
        children=0,
        buildings={},
        opening_stock={"R-001": Decimal("5")},
        treasury_balance=Decimal("0.00"),
        resource_prices={},
        scenario_parameters={"ChildToAdultMonthlyAgingRatePercent": 2.0},
    )

    # Independent of the default city.
    assert minimal.city_id != built.city.city_id
    assert minimal.scenario_id != built.city.scenario_id
    assert minimal.suffix != built.city.suffix

    # Sparse seeding: no CHILD row for 0, no Building rows, no price rows.
    population = _rows(
        session_factory,
        "SELECT t.Code, g.Count FROM dbo.PopulationGroup g JOIN dbo.PopulationGroupType t "
        "ON t.PopulationGroupTypeID = g.PopulationGroupTypeID WHERE g.CityID = ?",
        minimal.city_id,
    )
    assert population == [("ADULT", 7)]
    assert _scalar(session_factory, "SELECT COUNT(*) FROM dbo.Building WHERE CityID = ?", minimal.city_id) == 0
    assert (
        _scalar(
            session_factory,
            "SELECT COUNT(*) FROM dbo.MarketResourcePrice WHERE ScenarioID = ?",
            minimal.scenario_id,
        )
        == 0
    )

    inventory = _rows(
        session_factory,
        "SELECT r.Code, ci.Quantity FROM dbo.CityInventory ci JOIN dbo.Resource r "
        "ON r.ResourceID = ci.ResourceID WHERE ci.CityID = ?",
        minimal.city_id,
    )
    assert inventory == [("R-001", Decimal("5"))]

    # The Treasury and Market rows always exist (the services need them).
    assert _rows(
        session_factory, "SELECT Balance FROM dbo.Treasury WHERE TreasuryID = ?", minimal.treasury_id
    ) == [(Decimal("0.00"),)]
    assert _scalar(
        session_factory, "SELECT COUNT(*) FROM dbo.Market WHERE CityID = ?", minimal.city_id
    ) == 1

    run = _rows(
        session_factory,
        "SELECT StartSimulationDate, CurrentSimulationDate, CurrentSimulationTickID "
        "FROM dbo.SimulationRun WHERE SimulationRunID = ?",
        minimal.run_id,
    )
    assert run == [(datetime.date(1880, 3, 31), datetime.date(1880, 3, 31), 0)]
