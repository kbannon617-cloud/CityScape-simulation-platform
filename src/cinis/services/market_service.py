"""
Market service: executes buy/sell trades at fixed reference prices
(ADR-0008 - no supply/demand model). Both buy() and sell() are commands,
called on demand, like ConstructionService.order_project - nothing in
the design docs describes automatic NPC/AI trading, so there is no tick
step for this (Step 4.6a delivery note, flagged for the project owner).

buy(): city spends Treasury, gains the resource in inventory.
sell(): city gains Treasury, spends the resource from inventory.

Both deduct/credit Treasury through the existing TreasuryService and
inventory through InventoryService, so insufficient funds or stock fail
the same way they already do elsewhere (InsufficientInventoryError for
a sell that would go negative). Treasury currently allows a negative
balance - the same pre-existing M3 gap already flagged in
ConstructionService, not addressed here either.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from cinis.models.market import MarketTransaction
from cinis.repositories.market_repository import MarketRepository
from cinis.rules.ledger_rules import validate_ledger_trace
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService

MARKET_PURCHASE_CATEGORY = "MARKET_PURCHASE"
MARKET_SALE_CATEGORY = "MARKET_SALE"
TRANSACTION_TYPE_BUY = "Buy"
TRANSACTION_TYPE_SELL = "Sell"


class MarketService:
    def __init__(
        self,
        repository: MarketRepository,
        treasury_service: TreasuryService,
        inventory_service: InventoryService,
    ):
        self._repository = repository
        self._treasury_service = treasury_service
        self._inventory_service = inventory_service

    def buy(
        self,
        city_id: int,
        scenario_id: int,
        resource_code: str,
        quantity: Decimal,
        transaction_date: datetime.date,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> MarketTransaction:
        """Buy quantity of resource_code for city_id at the scenario's
        fixed reference price. Deducts Treasury, adds inventory, logs a
        MarketTransaction. Raises ValueError if quantity is not positive."""
        return self._execute(
            city_id, scenario_id, resource_code, quantity, transaction_date,
            simulation_run_id, simulation_tick_id,
            transaction_type=TRANSACTION_TYPE_BUY,
            treasury_category=MARKET_PURCHASE_CATEGORY,
            treasury_sign=-1,
            inventory_sign=1,
        )

    def sell(
        self,
        city_id: int,
        scenario_id: int,
        resource_code: str,
        quantity: Decimal,
        transaction_date: datetime.date,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> MarketTransaction:
        """Sell quantity of resource_code from city_id at the scenario's
        fixed reference price. Deducts inventory (raises
        InsufficientInventoryError if it would go negative), adds
        Treasury, logs a MarketTransaction."""
        return self._execute(
            city_id, scenario_id, resource_code, quantity, transaction_date,
            simulation_run_id, simulation_tick_id,
            transaction_type=TRANSACTION_TYPE_SELL,
            treasury_category=MARKET_SALE_CATEGORY,
            treasury_sign=1,
            inventory_sign=-1,
        )

    def _execute(
        self,
        city_id: int,
        scenario_id: int,
        resource_code: str,
        quantity: Decimal,
        transaction_date: datetime.date,
        simulation_run_id: int | None,
        simulation_tick_id: int | None,
        *,
        transaction_type: str,
        treasury_category: str,
        treasury_sign: int,
        inventory_sign: int,
    ) -> MarketTransaction:
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        validate_ledger_trace(simulation_run_id, simulation_tick_id)

        unit_price = self._repository.get_resource_price(scenario_id, resource_code)
        total_value = unit_price * quantity
        resource_id = self._inventory_service.get_resource_id(resource_code)

        # Inventory first: a sell that would go negative must abort
        # before Treasury is touched, matching ConstructionService's
        # materials-before-cost ordering.
        self._inventory_service.record_ledger_entry(
            city_id=city_id,
            resource_id=resource_id,
            amount=inventory_sign * quantity,
            entry_date=transaction_date,
            notes=f"Market {transaction_type.lower()}: {quantity} {resource_code}.",
            simulation_run_id=simulation_run_id,
            simulation_tick_id=simulation_tick_id,
        )
        self._treasury_service.record_ledger_entry(
            city_id=city_id,
            category_code=treasury_category,
            amount=treasury_sign * total_value,
            entry_date=transaction_date,
            simulation_run_id=simulation_run_id,
            simulation_tick_id=simulation_tick_id,
        )

        market = self._repository.get_market(city_id)
        return self._repository.record_transaction(
            market_id=market.MarketID,
            resource_id=resource_id,
            transaction_type=transaction_type,
            quantity=quantity,
            unit_price=unit_price,
            total_value=total_value,
            transaction_date=transaction_date,
        )
