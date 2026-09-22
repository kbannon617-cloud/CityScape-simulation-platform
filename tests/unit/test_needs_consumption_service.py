"""
Unit tests for NeedsConsumptionService against fakes (no database). Real SQL
behavior is covered in tests/integration/test_needs_consumption.py.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from cinis.repositories.need_resource_repository import MappedResource
from cinis.services.inventory_service import InsufficientInventoryError
from cinis.services.needs_consumption_service import NeedsConsumptionService
from cinis.services.needs_service import ExactNeedTotal

D = Decimal
DATE = datetime.date(1880, 1, 31)

WHEAT = MappedResource(1, "R-001")
TROUT = MappedResource(2, "R-002")
EGGS = MappedResource(9, "R-009")
LENTILS = MappedResource(10, "R-010")
TIMBER = MappedResource(4, "R-004")


class _FakeNeedsService:
    def __init__(self, totals):
        self._totals = totals

    def calculate_daily_need_totals_exact(self, city_id):
        return list(self._totals)


class _FakeMappingRepository:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_resources_by_need_type(self):
        return self._mapping


class _FakeInventoryService:
    """Mimics InventoryService: get_quantity by code, and a signed
    record_ledger_entry that refuses to go negative."""

    def __init__(self, stock):
        self.stock = dict(stock)  # resource_code -> Decimal
        self.calls = []  # every record_ledger_entry call, in order
        self._code_by_id = {m.resource_id: m.resource_code for m in (WHEAT, TROUT, EGGS, LENTILS, TIMBER)}

    def get_quantity(self, city_id, resource_code):
        return self.stock.get(resource_code, D("0"))

    def record_ledger_entry(self, **kwargs):
        code = self._code_by_id[kwargs["resource_id"]]
        new_quantity = self.stock.get(code, D("0")) + kwargs["amount"]
        if new_quantity < 0:
            raise InsufficientInventoryError(f"{code} would go negative")
        self.stock[code] = new_quantity
        self.calls.append({**kwargs, "resource_code": code})


def _service(totals, mapping, stock):
    inventory = _FakeInventoryService(stock)
    service = NeedsConsumptionService(
        _FakeNeedsService(totals), _FakeMappingRepository(mapping), inventory
    )
    return service, inventory


def _total(code, quantity, unit="KG"):
    return ExactNeedTotal(need_type_code=code, total_quantity=D(quantity), unit_code=unit)


FOOD_MAPPING = {"FOOD": [WHEAT, TROUT, EGGS, LENTILS]}


def _consume(service):
    return service.consume_daily_needs(city_id=1, entry_date=DATE)


def test_a_need_fully_met_by_the_first_resource_uses_only_that_resource():
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, {"R-001": D("500"), "R-002": D("500")})

    (result,) = _consume(service)

    assert result.need_type_code == "FOOD"
    assert (result.needed, result.consumed, result.shortfall) == (D("110.0000"), D("110.0000"), D("0"))
    assert [(c.resource_code, c.quantity) for c in result.consumption_by_resource] == [("R-001", D("110.0000"))]
    assert inventory.stock["R-001"] == D("390.0000")
    assert inventory.stock["R-002"] == D("500")  # untouched


def test_resources_are_drained_in_priority_order_until_the_need_is_met():
    stock = {"R-001": D("60"), "R-002": D("30"), "R-009": D("50"), "R-010": D("999")}
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, stock)

    (result,) = _consume(service)

    assert [(c.resource_code, c.quantity) for c in result.consumption_by_resource] == [
        ("R-001", D("60")),
        ("R-002", D("30")),
        ("R-009", D("20.0000")),
    ]
    assert [call["resource_code"] for call in inventory.calls] == ["R-001", "R-002", "R-009"]
    assert result.shortfall == 0
    assert inventory.stock["R-001"] == 0
    assert inventory.stock["R-002"] == 0
    assert inventory.stock["R-009"] == D("30.0000")
    assert inventory.stock["R-010"] == D("999")  # never reached


def test_a_shortfall_consumes_everything_available_and_reports_the_remainder():
    stock = {"R-001": D("60"), "R-002": D("30")}
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, stock)

    (result,) = _consume(service)

    assert result.needed == D("110.0000")
    assert result.consumed == D("90.0000")
    assert result.shortfall == D("20.0000")
    assert inventory.stock == {"R-001": D("0"), "R-002": D("0")}


def test_stock_never_goes_negative_even_with_no_stock_at_all():
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, {})

    (result,) = _consume(service)

    assert result.consumed == 0
    assert result.shortfall == D("110.0000")
    assert result.consumption_by_resource == ()
    assert inventory.calls == []


def test_resources_with_no_stock_are_skipped_without_zero_entries():
    stock = {"R-001": D("0"), "R-009": D("200")}
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, stock)

    (result,) = _consume(service)

    assert [c.resource_code for c in result.consumption_by_resource] == ["R-009"]
    assert len(inventory.calls) == 1
    assert all(call["amount"] != 0 for call in inventory.calls)


def test_a_need_type_with_no_mapping_is_skipped_entirely():
    totals = [_total("FOOD", "110"), _total("BASIC_GOODS", "22", "EA")]
    service, inventory = _service(totals, FOOD_MAPPING, {"R-001": D("500")})

    results = _consume(service)

    assert [r.need_type_code for r in results] == ["FOOD"]
    assert len(inventory.calls) == 1


def test_a_zero_need_produces_a_zero_result_and_no_ledger_entries():
    service, inventory = _service([_total("FOOD", "0")], FOOD_MAPPING, {"R-001": D("500")})

    (result,) = _consume(service)

    assert (result.needed, result.consumed, result.shortfall) == (D("0.0000"), D("0.0000"), D("0"))
    assert inventory.calls == []


def test_the_need_is_floored_to_four_decimals_never_rounded_up():
    service, inventory = _service([_total("FOOD", "10.00019")], FOOD_MAPPING, {"R-001": D("500")})

    (result,) = _consume(service)

    assert result.needed == D("10.0001")
    assert inventory.calls[0]["amount"] == D("-10.0001")


def test_need_types_are_processed_in_code_order_regardless_of_input_order():
    totals = [_total("HEATING", "88"), _total("FOOD", "110")]
    mapping = {"HEATING": [TIMBER], "FOOD": [WHEAT]}
    service, inventory = _service(totals, mapping, {"R-001": D("500"), "R-004": D("500")})

    results = _consume(service)

    assert [r.need_type_code for r in results] == ["FOOD", "HEATING"]
    assert [call["resource_code"] for call in inventory.calls] == ["R-001", "R-004"]


def test_each_ledger_entry_is_negative_dated_noted_and_traced():
    service, inventory = _service([_total("FOOD", "110")], FOOD_MAPPING, {"R-001": D("500")})

    service.consume_daily_needs(city_id=7, entry_date=DATE, simulation_run_id=3, simulation_tick_id=42)

    (call,) = inventory.calls
    assert call["city_id"] == 7
    assert call["resource_id"] == WHEAT.resource_id
    assert call["amount"] == D("-110.0000")
    assert call["entry_date"] == DATE
    assert call["notes"] == "Daily FOOD consumption."
    assert (call["simulation_run_id"], call["simulation_tick_id"]) == (3, 42)


def test_trace_defaults_to_none_when_not_supplied():
    service, inventory = _service([_total("FOOD", "1")], FOOD_MAPPING, {"R-001": D("5")})

    _consume(service)

    assert (inventory.calls[0]["simulation_run_id"], inventory.calls[0]["simulation_tick_id"]) == (None, None)


def test_the_same_resource_serving_two_needs_is_drawn_down_progressively():
    totals = [_total("FOOD", "60"), _total("HEATING", "60")]
    mapping = {"FOOD": [WHEAT], "HEATING": [WHEAT]}
    service, inventory = _service(totals, mapping, {"R-001": D("100")})

    food, heating = _consume(service)

    assert food.consumed == D("60.0000") and food.shortfall == 0
    assert heating.consumed == D("40.0000") and heating.shortfall == D("20.0000")
    assert inventory.stock["R-001"] == 0


def test_repeated_runs_with_identical_inputs_give_identical_results():
    def run():
        service, _ = _service(
            [_total("FOOD", "110")], FOOD_MAPPING, {"R-001": D("60"), "R-002": D("30"), "R-009": D("50")}
        )
        return _consume(service)

    assert run() == run()
