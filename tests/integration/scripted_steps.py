"""
M5 Step 5.3: the two TEST-ONLY scripted steps the vertical slice injects
into the real engine's step list, and the assembly of the full slice list.

WHAT THIS IS: MarketService.buy/sell and ConstructionService.order_project
are commands, not tick steps - nothing in src/ calls them automatically (M4
Step 4.6). To exercise them inside a real tick, the slice wraps them in two
throwaway TickSteps placed where Document 6's cycle puts "orders" (before
population/labor) and "market operations" (after needs consumption, before
the snapshot). One tick, one transaction, every ledger entry traced with
the tick's run/tick, and the snapshot sees the trades.

WHAT THIS IS NOT: a command queue or scheduler. It lives in tests/, nothing
in src/ imports it, and it must not be read as approval of a particular
command-queue design. Whether baseline runs (M6) get a real
scheduled-commands mechanism, and how a command issued outside a tick is
traced (the ledger trace requires tick >= 1), is an explicit M6 decision.

The steps call the same services the real steps use, wired the same way
(ConstructionService through the real construction step's own dependency
builder), on the tick's session. Like every step they do not commit; the
engine commits once or rolls the whole tick back.

The day's script is expressed with slice_oracle.Order and Trade, the same
types the oracle models, so executor and expectation cannot drift apart.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.market_repository import MarketRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.market_service import MarketService
from cinis.services.treasury_service import TreasuryService
from cinis.simulation.aging_step import build_aging_step_dependencies, make_aging_step
from cinis.simulation.construction_step import (
    build_construction_step_dependencies,
    make_construction_step,
)
from cinis.simulation.needs_step import build_needs_step_dependencies, make_needs_consumption_step
from cinis.simulation.production_step import build_production_step_dependencies, make_production_step
from cinis.simulation.snapshot_step import build_snapshot_step_dependencies, make_snapshot_step
from cinis.simulation.tick import TickContext, TickStep
from slice_oracle import Order, Trade

ORDERS_STEP_NAME = "ScriptedOrders"
TRADES_STEP_NAME = "ScriptedTrades"


def redirect_to_city(default_factory: Callable[[Session], object], city_id: int):
    """Wrap a real step's dependencies_factory so it targets an isolated Test
    city instead of the real primary-active city (the Step 4.7 pattern; the
    default factory still runs, and only city_id is replaced)."""

    def factory(session: Session):
        return dataclasses.replace(default_factory(session), city_id=city_id)

    return factory


def make_scripted_orders_step(city_id: int, orders: Sequence[Order]) -> TickStep:
    """Place each construction order on the tick's session, dated and traced
    to the tick it runs in."""

    def execute(context: TickContext) -> None:
        service = build_construction_step_dependencies(context.session).construction_service
        for order in orders:
            service.order_project(
                city_id=city_id,
                scenario_id=context.scenario_id,
                building_type_code=order.building_code,
                buildings_ordered=order.count,
                order_date=context.simulation_date,
                simulation_run_id=context.simulation_run_id,
                simulation_tick_id=context.simulation_tick_id,
            )

    return TickStep(name=ORDERS_STEP_NAME, execute=execute)


def make_scripted_trades_step(city_id: int, trades: Sequence[Trade]) -> TickStep:
    """Execute each market trade, in order, on the tick's session."""

    def execute(context: TickContext) -> None:
        session = context.session
        market = MarketService(
            MarketRepository(session),
            TreasuryService(TreasuryRepository(session)),
            InventoryService(InventoryRepository(session)),
        )
        for trade in trades:
            action = market.sell if trade.side == "sell" else market.buy
            action(
                city_id=city_id,
                scenario_id=context.scenario_id,
                resource_code=trade.resource_code,
                quantity=trade.quantity,
                transaction_date=context.simulation_date,
                simulation_run_id=context.simulation_run_id,
                simulation_tick_id=context.simulation_tick_id,
            )

    return TickStep(name=TRADES_STEP_NAME, execute=execute)


def build_slice_steps(
    city_id: int, orders: Sequence[Order], trades: Sequence[Trade]
) -> tuple[TickStep, ...]:
    """The real five steps, redirected to the Test city, with the two scripted
    steps inserted at their Document 6 positions:

        ScriptedOrders, <aging>, <production>, <construction>, <needs>,
        ScriptedTrades, <snapshot>
    """
    return (
        make_scripted_orders_step(city_id, orders),
        make_aging_step(redirect_to_city(build_aging_step_dependencies, city_id)),
        make_production_step(redirect_to_city(build_production_step_dependencies, city_id)),
        make_construction_step(redirect_to_city(build_construction_step_dependencies, city_id)),
        make_needs_consumption_step(redirect_to_city(build_needs_step_dependencies, city_id)),
        make_scripted_trades_step(city_id, trades),
        make_snapshot_step(redirect_to_city(build_snapshot_step_dependencies, city_id)),
    )
