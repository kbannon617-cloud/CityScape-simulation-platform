"""
M5 Step 5.3: the First Vertical Slice (Document 8: "end-to-end single-day
tick across population, production, inventory, and market").

One real SimulationEngine tick, on a month-boundary day (1880-01-31 ->
1880-02-01, the only kind of tick on which Aging, Production, Construction
and Snapshot all run), against the fully isolated synthetic Test city from
isolated_city.py. The real CityScape city and Cinis Baseline scenario are
never passed to the engine, and the final assertion proves they are
unchanged.

The day (Document 6 order; the two scripted steps are TEST-ONLY wrappers
around the real command services, see scripted_steps.py):

    ScriptedOrders -> Aging -> Production -> Construction -> NeedsConsumption
                   -> ScriptedTrades -> Snapshot

What makes this a proof and not just "it did not crash": every expectation
comes from slice_oracle.expected_day, an independent model fed ONLY by raw
SQL reads of the catalog and start state (never by the services under test),
and the committed end state is compared with it field by field - population,
buildings, inventory, treasury, the construction project, the market
transactions, the events, the snapshot - plus ledger invariants (inventory
and treasury equal the sum of their ledgers, every entry the tick wrote is
stamped with the tick's run/tick).

The second live test runs the same day with one trade that fails mid-tick and
proves the whole tick rolls back across every domain (Document 7: no partial
persistence after a failed tick), using real steps instead of fakes.

Run with `pytest -s tests/integration/test_vertical_slice.py` to print a
before/after report of the day.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cinis.config.settings import load_database_settings
from cinis.events.event_types import CONSTRUCTION_COMPLETED, NEEDS_SHORTFALL
from cinis.models.construction import STATUS_COMPLETE
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.services.inventory_service import InsufficientInventoryError, InventoryService
from cinis.simulation.engine import SimulationEngine, SimulationRunNotActiveError
from cinis.simulation.steps import build_default_tick_steps
from isolated_city import (
    SLICE_START_DATE,
    build_isolated_city,
    query_rows,
    query_scalar,
    real_city_fingerprint,
)
from scripted_steps import ORDERS_STEP_NAME, TRADES_STEP_NAME, build_slice_steps
from slice_oracle import BuildingSpec, Catalog, DayStart, ModelError, Order, Trade, expected_day

TICK_DATE = SLICE_START_DATE + datetime.timedelta(days=1)   # 1880-02-01
SNAPSHOT_RESOURCES = ("R-001", "R-002", "R-003", "R-004")    # what the Snapshot step records


def _dec(value) -> Decimal:
    return Decimal(str(value))


# --- No database needed ------------------------------------------------------


def test_slice_step_order_follows_the_default_list_with_scripted_steps_at_their_document_6_slots():
    """Guards against drift: if the real default step list ever changes, the
    slice must be revisited deliberately rather than silently diverge."""
    default_names = [step.name for step in build_default_tick_steps()]
    sliced = [step.name for step in build_slice_steps(city_id=1, orders=(), trades=())]

    # Orders first (before population/labor); trades after NeedsConsumption and
    # before Snapshot (Document 6: market operations follow consumption).
    needs_index = default_names.index("NeedsConsumption")
    assert sliced == (
        [ORDERS_STEP_NAME]
        + default_names[: needs_index + 1]
        + [TRADES_STEP_NAME]
        + default_names[needs_index + 1 :]
    )
    assert sliced[-1] == "Snapshot"


# --- The live slice ------------------------------------------------------------


@pytest.fixture(scope="module")
def session_factory(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    yield sessionmaker(bind=engine)
    engine.dispose()


def _read_catalog(sf, scenario_id: int) -> Catalog:
    """Global reference data plus the Test scenario's explicit prices, by raw SQL."""
    specs: dict[str, dict] = {}
    for code, workers, cost, timber, stone in query_rows(
        sf,
        "SELECT Code, WorkersPerBuilding, ConstructionCost, TimberRequiredPerBuilding, "
        "StoneRequiredPerBuilding FROM dbo.BuildingType",
    ):
        specs[code] = {
            "workers": int(workers), "cost": _dec(cost), "timber": _dec(timber),
            "stone": _dec(stone), "inputs": {}, "outputs": {},
        }
    for building_code, flow_type, resource_code, units in query_rows(
        sf,
        "SELECT bt.Code, pf.FlowType, r.Code, pf.UnitsPerBuildingPerMonth "
        "FROM dbo.ProductionFlow pf "
        "JOIN dbo.BuildingType bt ON bt.BuildingTypeID = pf.BuildingTypeID "
        "JOIN dbo.Resource r ON r.ResourceID = pf.ResourceID",
    ):
        specs[building_code]["inputs" if flow_type == "Input" else "outputs"][resource_code] = _dec(units)

    need_rates: dict[str, dict[str, Decimal]] = {}
    for need_code, group_code, rate in query_rows(
        sf,
        "SELECT nt.Code, g.Code, cr.QuantityPerPersonPerDay "
        "FROM dbo.NeedConsumptionRate cr "
        "JOIN dbo.NeedType nt ON nt.NeedTypeID = cr.NeedTypeID "
        "JOIN dbo.PopulationGroupType g ON g.PopulationGroupTypeID = cr.PopulationGroupTypeID",
    ):
        need_rates.setdefault(need_code, {})[group_code] = _dec(rate)

    need_resources: dict[str, list[str]] = {}
    for need_code, resource_code in query_rows(
        sf,
        "SELECT nt.Code, r.Code FROM dbo.NeedTypeResource ntr "
        "JOIN dbo.NeedType nt ON nt.NeedTypeID = ntr.NeedTypeID "
        "JOIN dbo.Resource r ON r.ResourceID = ntr.ResourceID "
        "ORDER BY nt.Code, ntr.ConsumptionPriority",
    ):
        need_resources.setdefault(need_code, []).append(resource_code)

    prices = {
        code: _dec(price)
        for code, price in query_rows(
            sf,
            "SELECT r.Code, p.UnitPrice FROM dbo.MarketResourcePrice p "
            "JOIN dbo.Resource r ON r.ResourceID = p.ResourceID WHERE p.ScenarioID = ?",
            scenario_id,
        )
    }
    return Catalog(
        buildings={
            code: BuildingSpec(
                workers=s["workers"], inputs=s["inputs"], outputs=s["outputs"],
                construction_cost=s["cost"], timber=s["timber"], stone=s["stone"],
            )
            for code, s in specs.items()
        },
        need_rates=need_rates,
        need_resources={code: tuple(resources) for code, resources in need_resources.items()},
        prices=prices,
    )


def _read_population(sf, city_id: int) -> dict[str, int]:
    return dict(
        query_rows(
            sf,
            "SELECT t.Code, g.Count FROM dbo.PopulationGroup g JOIN dbo.PopulationGroupType t "
            "ON t.PopulationGroupTypeID = g.PopulationGroupTypeID WHERE g.CityID = ?",
            city_id,
        )
    )


def _read_buildings(sf, city_id: int) -> dict[str, int]:
    return {
        code: count
        for code, count in query_rows(
            sf,
            "SELECT bt.Code, b.Count FROM dbo.Building b JOIN dbo.BuildingType bt "
            "ON bt.BuildingTypeID = b.BuildingTypeID WHERE b.CityID = ?",
            city_id,
        )
        if count > 0
    }


def _read_stock(sf, city_id: int) -> dict[str, Decimal]:
    return {
        code: _dec(quantity)
        for code, quantity in query_rows(
            sf,
            "SELECT r.Code, ci.Quantity FROM dbo.CityInventory ci JOIN dbo.Resource r "
            "ON r.ResourceID = ci.ResourceID WHERE ci.CityID = ?",
            city_id,
        )
    }


def _read_treasury(sf, treasury_id: int) -> Decimal:
    return _dec(query_scalar(sf, "SELECT Balance FROM dbo.Treasury WHERE TreasuryID = ?", treasury_id))


def _read_start(sf, city) -> DayStart:
    population = _read_population(sf, city.city_id)
    parameters = {
        key: _dec(value)
        for key, value in query_rows(
            sf,
            "SELECT ParameterKey, ParameterValue FROM dbo.ScenarioParameter WHERE ScenarioID = ?",
            city.scenario_id,
        )
    }
    return DayStart(
        adults=population["ADULT"],
        children=population["CHILD"],
        buildings=_read_buildings(sf, city.city_id),
        stock=_read_stock(sf, city.city_id),
        treasury=_read_treasury(sf, city.treasury_id),
        aging_rate_percent=parameters["ChildToAdultMonthlyAgingRatePercent"],
        participation_percent=parameters["AdultLaborParticipationRatePercent"],
        monthly_construction_budget=parameters["MonthlyConstructionBudget"],
        bonus_per_crew=parameters["ConstructionBonusPerCompletedCrew"],
    )


def _assert_same_stock(actual: dict[str, Decimal], expected: dict[str, Decimal], where: str) -> None:
    """Missing means zero (sparse seeding), so compare over the union of codes."""
    for code in sorted(set(actual) | set(expected)):
        assert actual.get(code, Decimal("0")) == expected.get(code, Decimal("0")), (
            f"{where}: {code} is {actual.get(code, Decimal('0'))}, expected {expected.get(code, Decimal('0'))}"
        )


def _report(start: DayStart, expected, result) -> str:
    lines = [
        "",
        f"=== M5 vertical slice: tick {result.simulation_tick_id} on {result.simulation_date} "
        f"(month boundary: {result.is_month_boundary}) ===",
        "steps:        " + " -> ".join(result.executed_steps),
        f"population:   adults {start.adults} -> {expected.adults}, children {start.children} -> "
        f"{expected.children}  ({expected.aged} aged)",
    ]
    for code, outcome in expected.production.items():
        lines.append(
            f"production:   {code} staffed {outcome.staffed}, in {dict(outcome.inputs)}, out {dict(outcome.outputs)}"
            + (f"  [{outcome.skipped_reason}]" if outcome.skipped_reason else "")
        )
    for need in expected.needs:
        lines.append(f"needs:        {need.need_code} needed {need.needed}, consumed {need.consumed}")
    for code, count in expected.completed:
        lines.append(f"construction: {count}x {code} completed this tick")
    for trade in expected.transactions:
        lines.append(
            f"market:       {trade.side} {trade.quantity} {trade.resource_code} @ {trade.unit_price} = {trade.total_value}"
        )
    lines.append(f"treasury:     {start.treasury} -> {expected.treasury}")
    for code in sorted(set(start.stock) | set(expected.stock)):
        lines.append(
            f"inventory:    {code:6} {start.stock.get(code, Decimal('0'))} -> {expected.stock.get(code, Decimal('0'))}"
        )
    return "\n".join(lines)


def test_one_boundary_day_runs_every_domain_end_to_end(session_factory):
    real_before = real_city_fingerprint(session_factory)
    city = build_isolated_city(session_factory, label="VSlice")

    catalog = _read_catalog(session_factory, city.scenario_id)
    start = _read_start(session_factory, city)

    # The day's script. Sell exactly what the Saw Mill makes (the model tells us
    # how much that is before anything runs); buy a fixed 100 Wheat.
    orders = (Order("B-007", 1),)
    lumber_made = expected_day(catalog, start, orders).stock.get("R-005", Decimal("0"))
    trades = (Trade("sell", "R-005", lumber_made), Trade("buy", "R-001", Decimal("100")))
    expected = expected_day(catalog, start, orders, trades)

    # Preconditions: every domain must have something observable to do, or this
    # would be a vacuous pass. If the catalog or stock changes so one of these
    # fails, the slice needs retuning - not the engine.
    assert expected.aged > 0, "no children age on this day, so Population is not exercised"
    assert expected.production["B-002"].outputs and expected.production["B-009"].outputs, "Production idle"
    assert expected.completed == [("B-007", 1)], "the Crew order must complete within the one tick"
    assert expected.needs and not expected.shortfalls, f"not a happy-path day: {expected.shortfalls}"
    assert lumber_made > 0

    steps = build_slice_steps(city.city_id, orders, trades)
    result = SimulationEngine(session_factory, steps).run_tick(city.run_id)
    print(_report(start, expected, result))

    # --- The tick itself -------------------------------------------------------
    assert result.simulation_tick_id == 1
    assert result.simulation_date == TICK_DATE
    assert result.is_month_boundary
    assert result.executed_steps == tuple(step.name for step in steps), "every step must run, in order"
    assert query_rows(
        session_factory,
        "SELECT CurrentSimulationDate, CurrentSimulationTickID, Status FROM dbo.SimulationRun "
        "WHERE SimulationRunID = ?",
        city.run_id,
    ) == [(TICK_DATE, 1, "Active")]

    # --- Committed end state matches the independent model --------------------
    population = _read_population(session_factory, city.city_id)
    assert (population["ADULT"], population["CHILD"]) == (expected.adults, expected.children)
    assert _read_buildings(session_factory, city.city_id) == expected.buildings
    end_stock = _read_stock(session_factory, city.city_id)
    _assert_same_stock(end_stock, expected.stock, "end-of-day inventory")
    end_treasury = _read_treasury(session_factory, city.treasury_id)
    assert end_treasury == expected.treasury

    # --- Construction: the whole project lifecycle inside one tick --------------
    crew = catalog.buildings["B-007"]
    assert query_rows(
        session_factory,
        "SELECT bt.Code, cp.BuildingsOrdered, cp.Status, cp.MonthsElapsed, cp.AdjustedDurationMonths, "
        "cp.OrderSimulationDate, cp.CompletedSimulationDate, cp.TotalConstructionCost, "
        "cp.TotalTimberRequired, cp.TotalStoneRequired "
        "FROM dbo.ConstructionProject cp JOIN dbo.BuildingType bt ON bt.BuildingTypeID = cp.BuildingTypeID "
        "WHERE cp.CityID = ?",
        city.city_id,
    ) == [("B-007", 1, STATUS_COMPLETE, 1, 1, TICK_DATE, TICK_DATE,
           crew.construction_cost, crew.timber, crew.stone)]

    # --- Events: exactly the completion, no shortfall ---------------------------
    events = query_rows(
        session_factory,
        "SELECT EventType, SimulationTickID, SimulationDate, CityID, Payload "
        "FROM dbo.SimulationEvent WHERE SimulationRunID = ? ORDER BY SimulationEventID",
        city.run_id,
    )
    assert [(e[0], e[1], e[2], e[3]) for e in events] == [
        (CONSTRUCTION_COMPLETED, 1, TICK_DATE, city.city_id)
    ], f"unexpected events (a {NEEDS_SHORTFALL} here would mean the day was not happy-path): {events}"
    payload = json.loads(events[0][4])
    assert (payload["BuildingTypeCode"], payload["BuildingsOrdered"]) == ("B-007", 1)

    # --- Market: both trades recorded, in order, at the fixed prices ------------
    assert query_rows(
        session_factory,
        "SELECT mt.TransactionType, r.Code, mt.Quantity, mt.UnitPrice, mt.TotalValue, mt.TransactionDate "
        "FROM dbo.MarketTransaction mt JOIN dbo.Resource r ON r.ResourceID = mt.ResourceID "
        "WHERE mt.MarketID = ? ORDER BY mt.MarketTransactionID",
        city.market_id,
    ) == [
        ("Sell" if t.side == "sell" else "Buy", t.resource_code, t.quantity, t.unit_price, t.total_value, TICK_DATE)
        for t in expected.transactions
    ]

    # --- Ledger invariants --------------------------------------------------------
    # Inventory: every quantity equals the sum of its ledger (the ledger is the truth).
    for code, quantity, ledger_sum in query_rows(
        session_factory,
        "SELECT r.Code, ci.Quantity, SUM(le.Amount) FROM dbo.CityInventory ci "
        "JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID "
        "JOIN dbo.InventoryLedgerEntry le ON le.CityInventoryID = ci.CityInventoryID "
        "WHERE ci.CityID = ? GROUP BY r.Code, ci.Quantity",
        city.city_id,
    ):
        assert quantity == ledger_sum, f"{code}: quantity {quantity} != ledger sum {ledger_sum}"

    # Everything the tick wrote is stamped (run, tick 1, the tick's date); the only
    # untraced entries are the builder's opening stock, dated the day before.
    traced = query_rows(
        session_factory,
        "SELECT DISTINCT le.SimulationRunID, le.SimulationTickID, le.EntryDate "
        "FROM dbo.InventoryLedgerEntry le JOIN dbo.CityInventory ci ON ci.CityInventoryID = le.CityInventoryID "
        "WHERE ci.CityID = ? AND le.SimulationRunID IS NOT NULL",
        city.city_id,
    )
    assert traced == [(city.run_id, 1, TICK_DATE)]
    untraced = query_rows(
        session_factory,
        "SELECT COUNT(*), MIN(le.EntryDate), MAX(le.EntryDate) "
        "FROM dbo.InventoryLedgerEntry le JOIN dbo.CityInventory ci ON ci.CityInventoryID = le.CityInventoryID "
        "WHERE ci.CityID = ? AND le.SimulationRunID IS NULL",
        city.city_id,
    )
    opening_day = SLICE_START_DATE - datetime.timedelta(days=1)
    assert untraced == [(len(start.stock), opening_day, opening_day)]

    # Treasury: balance = opening balance + its ledger, and the ledger is exactly the trades.
    treasury_ledger = query_rows(
        session_factory,
        "SELECT tc.Code, le.Amount, le.SimulationRunID, le.SimulationTickID, le.EntryDate "
        "FROM dbo.TreasuryLedgerEntry le JOIN dbo.TreasuryCategoryType tc "
        "ON tc.TreasuryCategoryTypeID = le.TreasuryCategoryTypeID "
        "WHERE le.TreasuryID = ? ORDER BY le.TreasuryLedgerEntryID",
        city.treasury_id,
    )
    assert treasury_ledger == [
        (
            "MARKET_SALE" if t.side == "sell" else "MARKET_PURCHASE",
            t.total_value if t.side == "sell" else -t.total_value,
            city.run_id, 1, TICK_DATE,
        )
        for t in expected.transactions
    ]
    assert end_treasury == start.treasury + sum(_dec(row[1]) for row in treasury_ledger)

    # --- Snapshot: one row, capturing end-of-tick state (after the trades) --------
    snapshots = query_rows(
        session_factory,
        "SELECT SimulationTickID, SimulationDate, CityID, Payload FROM dbo.CitySnapshot "
        "WHERE SimulationRunID = ?",
        city.run_id,
    )
    assert [(s[0], s[1], s[2]) for s in snapshots] == [(1, TICK_DATE, city.city_id)]
    snapshot = json.loads(snapshots[0][3])
    assert (snapshot["AdultCount"], snapshot["ChildCount"]) == (expected.adults, expected.children)
    assert _dec(snapshot["TreasuryBalance"]) == expected.treasury
    assert snapshot["Buildings"] == expected.buildings
    assert snapshot["Vehicles"] == {}
    assert set(snapshot["Inventory"]) == set(SNAPSHOT_RESOURCES)
    _assert_same_stock(
        {code: _dec(value) for code, value in snapshot["Inventory"].items()},
        {code: expected.stock.get(code, Decimal("0")) for code in SNAPSHOT_RESOURCES},
        "snapshot inventory",
    )

    # --- The real CityScape was never touched --------------------------------------
    assert real_city_fingerprint(session_factory) == real_before


def _city_state(sf, city) -> dict:
    """Everything the slice's day could change for the Test city, across every
    domain, in one comparable dict. Row counts catch rows a rollback should
    have removed (a ledger entry, an event, a project, a snapshot, a trade,
    even an inventory row created for a resource the city never held)."""
    cid, rid = city.city_id, city.run_id
    return {
        "population": _read_population(sf, cid),
        "buildings": _read_buildings(sf, cid),
        "stock": _read_stock(sf, cid),
        "treasury": _read_treasury(sf, city.treasury_id),
        "inventory_rows": query_scalar(sf, "SELECT COUNT(*) FROM dbo.CityInventory WHERE CityID = ?", cid),
        "inventory_ledger_rows": query_scalar(
            sf,
            "SELECT COUNT(*) FROM dbo.InventoryLedgerEntry le JOIN dbo.CityInventory ci "
            "ON ci.CityInventoryID = le.CityInventoryID WHERE ci.CityID = ?",
            cid,
        ),
        "treasury_ledger_rows": query_scalar(
            sf, "SELECT COUNT(*) FROM dbo.TreasuryLedgerEntry WHERE TreasuryID = ?", city.treasury_id
        ),
        "market_transactions": query_scalar(
            sf, "SELECT COUNT(*) FROM dbo.MarketTransaction WHERE MarketID = ?", city.market_id
        ),
        "construction_projects": query_scalar(
            sf, "SELECT COUNT(*) FROM dbo.ConstructionProject WHERE CityID = ?", cid
        ),
        "events": query_scalar(sf, "SELECT COUNT(*) FROM dbo.SimulationEvent WHERE SimulationRunID = ?", rid),
        "snapshots": query_scalar(sf, "SELECT COUNT(*) FROM dbo.CitySnapshot WHERE SimulationRunID = ?", rid),
    }


def test_a_trade_failing_mid_tick_rolls_back_every_domain(session_factory):
    real_before = real_city_fingerprint(session_factory)
    city = build_isolated_city(session_factory, label="VRollback")

    catalog = _read_catalog(session_factory, city.scenario_id)
    start = _read_start(session_factory, city)
    orders = (Order("B-007", 1),)
    lumber_made = expected_day(catalog, start, orders).stock.get("R-005", Decimal("0"))
    happy_adults = expected_day(catalog, start, orders).adults
    assert lumber_made > 0

    # The script: a perfectly good buy FIRST, then a sale of one more Lumber than
    # the Saw Mill made. The buy is already staged inside the tick's open
    # transaction when the sale fails - it must be rolled back with everything else.
    bad_trades = (
        Trade("buy", "R-001", Decimal("100")),
        Trade("sell", "R-005", lumber_made + 1),
    )
    with pytest.raises(ModelError, match="stock would go negative"):
        expected_day(catalog, start, orders, bad_trades)   # the model rejects this day too

    # Instrument every step to record that it started and, just before the failing
    # trade step runs, what is staged in the still-open transaction. That proves
    # real work in several domains existed to be rolled back (not a vacuous pass).
    started: list[str] = []
    staged: dict = {}

    def instrument(step):
        original = step.execute

        def execute(context):
            started.append(step.name)
            if step.name == TRADES_STEP_NAME:
                staged["adults"] = (
                    PopulationRepository(context.session).get_group(city.city_id, "ADULT").Count
                )
                staged["lumber"] = InventoryService(InventoryRepository(context.session)).get_quantity(
                    city.city_id, "R-005"
                )
            original(context)

        return dataclasses.replace(step, execute=execute)

    steps = tuple(instrument(step) for step in build_slice_steps(city.city_id, orders, bad_trades))
    engine = SimulationEngine(session_factory, steps)
    before = _city_state(session_factory, city)

    with pytest.raises(InsufficientInventoryError):
        engine.run_tick(city.run_id)

    # Everything up to and including the failing step started; the snapshot never did.
    all_names = [step.name for step in steps]
    assert started == all_names[:-1] and all_names[-1] == "Snapshot"
    # Mid-tick, the open transaction really held changes from earlier domains.
    assert staged["adults"] == happy_adults > start.adults, "aging was not staged before the failure"
    assert staged["lumber"] == lumber_made, "production was not staged before the failure"

    # Afterwards NOTHING from the tick survives, in any domain.
    assert _city_state(session_factory, city) == before

    # The run is marked Failed in its own transaction, and still sits at tick 0 / start date.
    assert query_rows(
        session_factory,
        "SELECT CurrentSimulationDate, CurrentSimulationTickID, Status FROM dbo.SimulationRun "
        "WHERE SimulationRunID = ?",
        city.run_id,
    ) == [(city.start_date, 0, "Failed")]

    # A Failed run refuses further ticks, and refusing changes nothing.
    with pytest.raises(SimulationRunNotActiveError):
        engine.run_tick(city.run_id)
    assert _city_state(session_factory, city) == before

    # The real CityScape was never touched by the failed tick either.
    assert real_city_fingerprint(session_factory) == real_before
