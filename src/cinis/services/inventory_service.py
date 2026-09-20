"""
Inventory service: the only place that should ever change
CityInventory.Quantity. Every change goes through record_ledger_entry so
the append-only InventoryLedgerEntry history and the current-state
Quantity never drift apart - mirrors TreasuryService exactly, with one
addition: since "non-negative inventory" is a Document 7 first-class
invariant (unlike Treasury.Balance, which may legitimately go negative),
this service checks the resulting quantity BEFORE writing, raising a
clear application-level error rather than relying solely on the
database's CHECK constraint to reject it after the fact.

Standalone and callable now, ahead of any tick engine - Milestone 4's
SimulationEngine will call this for production output/input consumption
once it exists.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from cinis.repositories.inventory_repository import InventoryRepository
from cinis.rules.ledger_rules import validate_ledger_trace


class InsufficientInventoryError(RuntimeError):
    """Raised when a ledger entry would take a resource's quantity
    negative. Callers should catch this and decide what to do (partial
    consumption, skip production, etc.) rather than have the database
    silently reject the transaction with a less specific error."""


@dataclass(frozen=True)
class InventoryLedgerEntryResult:
    new_quantity: Decimal
    entry_amount: Decimal
    resource_id: int


class InventoryService:
    def __init__(self, repository: InventoryRepository):
        self._repository = repository

    def get_quantity(self, city_id: int, resource_code: str) -> Decimal:
        return self._repository.get_quantity(city_id, resource_code)

    def record_ledger_entry(
        self,
        city_id: int,
        resource_id: int,
        amount: Decimal,
        entry_date: datetime.date,
        notes: str | None = None,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> InventoryLedgerEntryResult:
        """Record a signed ledger entry and update the running quantity.

        amount is signed: positive increases quantity (e.g. production
        output, opening stock), negative decreases it (e.g. consumption).
        Raises InsufficientInventoryError rather than letting quantity go
        negative. Does not commit; the caller owns the transaction
        boundary, consistent with TreasuryService and PopulationService.

        simulation_run_id and simulation_tick_id (ADR-0009 Decision 3) are
        supplied together by the tick engine, or both omitted; a ValueError
        is raised before anything is staged if only one is given.
        """
        validate_ledger_trace(simulation_run_id, simulation_tick_id)
        inventory = self._repository.get_or_create_inventory(city_id, resource_id)

        resulting_quantity = inventory.Quantity + amount
        if resulting_quantity < 0:
            raise InsufficientInventoryError(
                f"Cannot apply amount={amount} to CityID={city_id}, "
                f"ResourceID={resource_id}: current quantity is "
                f"{inventory.Quantity}, resulting quantity {resulting_quantity} "
                "would be negative."
            )

        self._repository.add_ledger_entry(
            city_inventory_id=inventory.CityInventoryID,
            entry_date=entry_date,
            amount=amount,
            notes=notes,
            simulation_run_id=simulation_run_id,
            simulation_tick_id=simulation_tick_id,
        )

        inventory.Quantity = resulting_quantity

        return InventoryLedgerEntryResult(
            new_quantity=inventory.Quantity,
            entry_amount=amount,
            resource_id=resource_id,
        )
