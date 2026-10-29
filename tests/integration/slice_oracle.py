"""
M5 Step 5.3: an independent model of the vertical-slice day.

The live slice test (test_vertical_slice.py) runs the REAL engine and steps
against a synthetic Test city, then compares the committed database state
with what this module says the day should produce. It is a "shadow model":
written from the documented rules (ADR-0008/0009/0010/0011, Document 6) with
its own hand-written floor arithmetic, and it never imports or calls the
services, rules or repositories under test. If the two disagree, either the
engine composes the steps wrongly or one side misreads a rule - both worth
knowing, and neither is hidden by the test sharing code with the thing it
checks.

It is pure Python with no database access, so its own arithmetic is tested
without SQL Server (test_slice_oracle.py), including against the real
seeded catalog numbers.

The day it models, in the order the slice test assembles the steps
(Document 6: orders first, market after needs, snapshot last):

    1. Orders        - construction orders: materials and cost deducted now
    2. Aging         - floor(children x rate%) children become adults
    3. Production    - labor pool first-come-first-served by building code;
                       inputs all-or-nothing per building type
    4. Construction  - month-boundary advance: a project whose duration is
                       met completes and adds its buildings
    5. Needs         - per-need totals floored to 4 decimals, drained in
                       priority order; unmapped needs skipped; shortfalls
                       recorded, never fatal
    6. Trades        - fixed reference prices; sells need stock, buys need
                       treasury (a model that would go negative is not a
                       happy-path day and raises ModelError)

The Order and Trade types are shared with scripted_steps.py, so the steps
and this model are driven by one definition of the day's script.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal

LEDGER_PRECISION = Decimal("0.0001")

# Resource and building codes the construction rules name explicitly.
TIMBER_CODE = "R-004"
STONE_CODE = "R-003"
CONSTRUCTION_CREW_CODE = "B-007"


class ModelError(ValueError):
    """The scripted day is not a valid happy-path day for this model (for
    example a sale that would take stock below zero). Raised by the model,
    never by the engine."""


@dataclass(frozen=True)
class Order:
    """A construction order, issued at the start of the day."""

    building_code: str
    count: int = 1


@dataclass(frozen=True)
class Trade:
    """A market trade, issued after needs consumption. side is 'sell' or 'buy'."""

    side: str
    resource_code: str
    quantity: Decimal

    def __post_init__(self):
        if self.side not in ("sell", "buy"):
            raise ValueError(f"side must be 'sell' or 'buy', got {self.side!r}")


@dataclass(frozen=True)
class BuildingSpec:
    workers: int
    inputs: dict[str, Decimal] = field(default_factory=dict)   # resource code -> units/building/month
    outputs: dict[str, Decimal] = field(default_factory=dict)
    construction_cost: Decimal = Decimal("0")
    timber: Decimal = Decimal("0")
    stone: Decimal = Decimal("0")


@dataclass(frozen=True)
class Catalog:
    """Global reference data plus the Test scenario's explicit prices."""

    buildings: dict[str, BuildingSpec]
    need_rates: dict[str, dict[str, Decimal]]       # need code -> group code -> per person per day
    need_resources: dict[str, tuple[str, ...]]      # need code -> resource codes, priority order
    prices: dict[str, Decimal]                      # resource code -> fixed unit price


@dataclass(frozen=True)
class DayStart:
    adults: int
    children: int
    buildings: dict[str, int]
    stock: dict[str, Decimal]
    treasury: Decimal
    aging_rate_percent: Decimal
    participation_percent: Decimal
    monthly_construction_budget: Decimal
    bonus_per_crew: Decimal


@dataclass(frozen=True)
class ProductionOutcome:
    staffed: int
    workers_used: int
    inputs: dict[str, Decimal]
    outputs: dict[str, Decimal]
    skipped_reason: str | None = None


@dataclass(frozen=True)
class NeedOutcome:
    need_code: str
    needed: Decimal
    consumed: Decimal

    @property
    def shortfall(self) -> Decimal:
        return self.needed - self.consumed


@dataclass(frozen=True)
class TradeOutcome:
    side: str
    resource_code: str
    quantity: Decimal
    unit_price: Decimal
    total_value: Decimal


@dataclass(frozen=True)
class ExpectedDay:
    adults: int
    children: int
    aged: int
    buildings: dict[str, int]
    stock: dict[str, Decimal]
    treasury: Decimal
    production: dict[str, ProductionOutcome]
    needs: list[NeedOutcome]
    transactions: list[TradeOutcome]
    completed: list[tuple[str, int]]                       # (building code, count)
    in_progress: list[tuple[str, int, int, int]]           # (code, count, duration, months elapsed)

    @property
    def shortfalls(self) -> list[NeedOutcome]:
        return [n for n in self.needs if n.shortfall > 0]


def _floor4(value: Decimal) -> Decimal:
    return value.quantize(LEDGER_PRECISION, rounding=ROUND_FLOOR)


def _floor_int(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _require_non_negative(stock: dict[str, Decimal], treasury: Decimal, where: str) -> None:
    negative = {code: qty for code, qty in stock.items() if qty < 0}
    if negative:
        raise ModelError(f"stock would go negative {where}: {negative}")
    if treasury < 0:
        raise ModelError(f"treasury would go negative {where}: {treasury}")


def expected_day(
    catalog: Catalog,
    start: DayStart,
    orders: tuple[Order, ...] = (),
    trades: tuple[Trade, ...] = (),
) -> ExpectedDay:
    stock = {code: Decimal(qty) for code, qty in start.stock.items()}
    buildings = {code: n for code, n in start.buildings.items() if n > 0}
    treasury = Decimal(start.treasury)
    adults, children = start.adults, start.children

    # 1. Orders: materials and cost leave immediately; duration is fixed now.
    projects: list[list] = []   # [code, count, duration, months_elapsed]
    for order in orders:
        spec = catalog.buildings[order.building_code]
        quantity = Decimal(order.count)
        total_cost = spec.construction_cost * quantity
        base = 1 if total_cost <= 0 else max(1, math.ceil(total_cost / start.monthly_construction_budget))
        bonus = Decimal(start.buildings.get(CONSTRUCTION_CREW_CODE, 0)) * start.bonus_per_crew
        duration = max(1, math.ceil(Decimal(base) / (Decimal(1) + bonus)))
        stock[TIMBER_CODE] = stock.get(TIMBER_CODE, Decimal("0")) - spec.timber * quantity
        stock[STONE_CODE] = stock.get(STONE_CODE, Decimal("0")) - spec.stone * quantity
        treasury -= total_cost
        projects.append([order.building_code, order.count, duration, 0])
    _require_non_negative(stock, treasury, "after orders")

    # 2. Aging: floor, remainder dropped (not carried).
    aged = _floor_int(Decimal(children) * start.aging_rate_percent / Decimal(100))
    children -= aged
    adults += aged

    # 3. Production: shared labor pool, first-come-first-served by code.
    labor = _floor_int(Decimal(adults) * start.participation_percent / Decimal(100))
    production: dict[str, ProductionOutcome] = {}
    for code in sorted(buildings):
        owned = buildings[code]
        spec = catalog.buildings[code]
        staffed = owned if spec.workers == 0 else min(owned, labor // spec.workers)
        if staffed <= 0:
            production[code] = ProductionOutcome(0, 0, {}, {}, "No labor available")
            continue
        workers_used = staffed * spec.workers
        planned = {res: units * staffed for res, units in spec.inputs.items()}
        if any(stock.get(res, Decimal("0")) < needed for res, needed in planned.items()):
            labor -= workers_used   # labor is spent even when the building idles
            production[code] = ProductionOutcome(staffed, workers_used, {}, {}, "Insufficient input inventory")
            continue
        for res, amount in planned.items():
            stock[res] -= amount
        produced = {res: units * staffed for res, units in spec.outputs.items()}
        for res, amount in produced.items():
            stock[res] = stock.get(res, Decimal("0")) + amount
        labor -= workers_used
        production[code] = ProductionOutcome(staffed, workers_used, planned, produced)
    _require_non_negative(stock, treasury, "after production")

    # 4. Construction advance (month boundary): complete what has reached its duration.
    completed: list[tuple[str, int]] = []
    in_progress: list[tuple[str, int, int, int]] = []
    for code, count, duration, elapsed in projects:
        elapsed += 1
        if elapsed >= duration:
            buildings[code] = buildings.get(code, 0) + count
            completed.append((code, count))
        else:
            in_progress.append((code, count, duration, elapsed))

    # 5. Needs: per-need totals from post-aging headcounts, drained in priority order.
    headcount = {"ADULT": adults, "CHILD": children}
    needs: list[NeedOutcome] = []
    for need_code in sorted(catalog.need_rates):
        mapped = catalog.need_resources.get(need_code)
        if not mapped:
            continue   # unmapped need types are skipped, not an error (ADR-0010)
        total = sum(
            (rate * headcount.get(group, 0) for group, rate in catalog.need_rates[need_code].items()),
            Decimal("0"),
        )
        needed = _floor4(total)
        remaining = needed
        for res in mapped:
            if remaining <= 0:
                break
            take = min(remaining, stock.get(res, Decimal("0")))
            if take <= 0:
                continue
            stock[res] -= take
            remaining -= take
        needs.append(NeedOutcome(need_code, needed, needed - remaining))
    _require_non_negative(stock, treasury, "after needs")

    # 6. Trades at fixed reference prices.
    transactions: list[TradeOutcome] = []
    for trade in trades:
        unit_price = catalog.prices[trade.resource_code]
        total_value = unit_price * trade.quantity
        if trade.side == "sell":
            stock[trade.resource_code] = stock.get(trade.resource_code, Decimal("0")) - trade.quantity
            treasury += total_value
        else:
            stock[trade.resource_code] = stock.get(trade.resource_code, Decimal("0")) + trade.quantity
            treasury -= total_value
        _require_non_negative(stock, treasury, f"after {trade.side} {trade.quantity} {trade.resource_code}")
        transactions.append(TradeOutcome(trade.side, trade.resource_code, trade.quantity, unit_price, total_value))

    return ExpectedDay(
        adults=adults,
        children=children,
        aged=aged,
        buildings=buildings,
        stock=stock,
        treasury=treasury,
        production=production,
        needs=needs,
        transactions=transactions,
        completed=completed,
        in_progress=in_progress,
    )
