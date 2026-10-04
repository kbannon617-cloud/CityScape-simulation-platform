"""Unit tests for MarketService.buy/sell against fakes (no database)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from cinis.services.market_service import MarketService

D = Decimal
DATE = datetime.date(1880, 2, 1)


@dataclass
class _FakeMarket:
    MarketID: int = 9


class _FakeMarketRepository:
    def __init__(self, price=D("5.00")):
        self._price = price
        self.transactions = []

    def get_resource_price(self, scenario_id, resource_code):
        return self._price

    def get_market(self, city_id):
        return _FakeMarket()

    def record_transaction(self, **kwargs):
        self.transactions.append(kwargs)
        return kwargs


class _FakeTreasuryService:
    def __init__(self):
        self.entries = []

    def record_ledger_entry(self, **kwargs):
        self.entries.append(kwargs)


class _FakeInventoryService:
    def __init__(self):
        self.entries = []

    def get_resource_id(self, code):
        return {"R-001": 1}[code]

    def record_ledger_entry(self, **kwargs):
        self.entries.append(kwargs)


def _build():
    market_repo = _FakeMarketRepository()
    treasury = _FakeTreasuryService()
    inventory = _FakeInventoryService()
    return MarketService(market_repo, treasury, inventory), market_repo, treasury, inventory


def test_buy_deducts_treasury_adds_inventory_and_logs_a_buy_transaction():
    service, market_repo, treasury, inventory = _build()

    service.buy(1, 9, "R-001", D("10"), DATE)

    assert treasury.entries[0]["amount"] == D("-50.00")
    assert treasury.entries[0]["category_code"] == "MARKET_PURCHASE"
    assert inventory.entries[0]["amount"] == D("10")
    (txn,) = market_repo.transactions
    assert txn["transaction_type"] == "Buy"
    assert txn["total_value"] == D("50.00")


def test_sell_credits_treasury_removes_inventory_and_logs_a_sell_transaction():
    service, market_repo, treasury, inventory = _build()

    service.sell(1, 9, "R-001", D("10"), DATE)

    assert treasury.entries[0]["amount"] == D("50.00")
    assert treasury.entries[0]["category_code"] == "MARKET_SALE"
    assert inventory.entries[0]["amount"] == D("-10")
    assert market_repo.transactions[0]["transaction_type"] == "Sell"


def test_inventory_is_deducted_before_treasury_on_a_sell():
    service, *_, treasury, inventory = _build()
    service.sell(1, 9, "R-001", D("10"), DATE)
    assert len(inventory.entries) == 1 and len(treasury.entries) == 1


@pytest.mark.parametrize("quantity", [D("0"), D("-5")])
def test_non_positive_quantity_raises_before_anything_is_staged(quantity):
    service, market_repo, treasury, inventory = _build()
    with pytest.raises(ValueError, match="positive"):
        service.buy(1, 9, "R-001", quantity, DATE)
    assert treasury.entries == [] and inventory.entries == [] and market_repo.transactions == []


def test_partial_trace_raises_before_anything_is_staged():
    service, market_repo, treasury, inventory = _build()
    with pytest.raises(ValueError, match="together"):
        service.buy(1, 9, "R-001", D("10"), DATE, simulation_tick_id=3)
    assert treasury.entries == []


def test_trace_ids_are_forwarded_to_both_ledger_writes():
    service, *_, treasury, inventory = _build()
    service.buy(1, 9, "R-001", D("10"), DATE, simulation_run_id=7, simulation_tick_id=3)
    assert treasury.entries[0]["simulation_run_id"] == 7
    assert inventory.entries[0]["simulation_tick_id"] == 3
