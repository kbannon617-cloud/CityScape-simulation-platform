"""
Unit tests for InventoryService's orchestration logic, using a minimal
fake repository rather than a real database.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from cinis.services.inventory_service import InsufficientInventoryError, InventoryService


@dataclass
class _FakeInventory:
    CityInventoryID: int
    Quantity: Decimal


@dataclass
class _FakeRepository:
    quantity: Decimal
    inventory: _FakeInventory = field(init=False)
    ledger_entries: list = field(default_factory=list)

    def __post_init__(self):
        self.inventory = _FakeInventory(CityInventoryID=1, Quantity=self.quantity)

    def get_or_create_inventory(self, city_id: int, resource_id: int):
        return self.inventory

    def add_ledger_entry(self, city_inventory_id, entry_date, amount, notes=None):
        self.ledger_entries.append((city_inventory_id, entry_date, amount, notes))


def test_record_positive_entry_increases_quantity():
    repo = _FakeRepository(quantity=Decimal("100"))
    service = InventoryService(repo)

    result = service.record_ledger_entry(
        city_id=1, resource_id=1, amount=Decimal("50"), entry_date=datetime.date(2026, 1, 1)
    )

    assert result.new_quantity == Decimal("150")
    assert repo.inventory.Quantity == Decimal("150")
    assert len(repo.ledger_entries) == 1


def test_record_negative_entry_decreases_quantity():
    repo = _FakeRepository(quantity=Decimal("100"))
    service = InventoryService(repo)

    result = service.record_ledger_entry(
        city_id=1, resource_id=1, amount=Decimal("-30"), entry_date=datetime.date(2026, 1, 1)
    )

    assert result.new_quantity == Decimal("70")


def test_record_entry_that_would_go_negative_raises_and_does_not_mutate():
    repo = _FakeRepository(quantity=Decimal("10"))
    service = InventoryService(repo)

    with pytest.raises(InsufficientInventoryError):
        service.record_ledger_entry(
            city_id=1, resource_id=1, amount=Decimal("-15"), entry_date=datetime.date(2026, 1, 1)
        )

    # Quantity must be unchanged, and no ledger entry should have been written.
    assert repo.inventory.Quantity == Decimal("10")
    assert len(repo.ledger_entries) == 0


def test_record_entry_that_exactly_zeroes_out_is_allowed():
    repo = _FakeRepository(quantity=Decimal("10"))
    service = InventoryService(repo)

    result = service.record_ledger_entry(
        city_id=1, resource_id=1, amount=Decimal("-10"), entry_date=datetime.date(2026, 1, 1)
    )

    assert result.new_quantity == Decimal("0")
