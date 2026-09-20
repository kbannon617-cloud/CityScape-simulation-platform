"""
Inventory repository. Isolates all SQL access for CityInventory and
InventoryLedgerEntry, per Document 6's layering. Mirrors
TreasuryRepository's shape.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.models.inventory import CityInventory, InventoryLedgerEntry


class CityInventoryNotFoundError(RuntimeError):
    """Raised when a requested (city, resource) inventory row does not
    exist. A missing row means zero stock at the data level (per the
    sparse-seeding convention), but callers that need to write a ledger
    entry require a real row to attach it to - get_or_create_inventory
    handles that distinction explicitly rather than silently creating
    rows on every read."""


class InventoryRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_quantity(self, city_id: int, resource_code: str) -> Decimal:
        """Return the current quantity, or 0 if no row exists yet (a
        missing row means zero stock, per the sparse-seeding convention
        used since migration 0012)."""
        inventory = self._get_inventory_row(city_id, resource_code)
        return inventory.Quantity if inventory is not None else Decimal("0")

    def get_or_create_inventory(self, city_id: int, resource_id: int) -> CityInventory:
        """Return the CityInventory row for (city, resource), creating it
        at zero quantity first if it doesn't exist yet. Used by the
        service layer before writing a ledger entry, so every ledger
        entry always has a real row to attach to."""
        inventory = (
            self._session.query(CityInventory)
            .filter(CityInventory.CityID == city_id, CityInventory.ResourceID == resource_id)
            .one_or_none()
        )
        if inventory is None:
            inventory = CityInventory(CityID=city_id, ResourceID=resource_id, Quantity=Decimal("0"))
            self._session.add(inventory)
            self._session.flush()
        return inventory

    def add_ledger_entry(
        self,
        city_inventory_id: int,
        entry_date: datetime.date,
        amount: Decimal,
        notes: str | None = None,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> None:
        self._session.add(
            InventoryLedgerEntry(
                CityInventoryID=city_inventory_id,
                EntryDate=entry_date,
                Amount=amount,
                Notes=notes,
                SimulationRunID=simulation_run_id,
                SimulationTickID=simulation_tick_id,
            )
        )

    def _get_inventory_row(self, city_id: int, resource_code: str) -> CityInventory | None:
        from cinis.models.inventory import Resource

        return (
            self._session.query(CityInventory)
            .join(Resource, Resource.ResourceID == CityInventory.ResourceID)
            .filter(CityInventory.CityID == city_id, Resource.Code == resource_code)
            .one_or_none()
        )
