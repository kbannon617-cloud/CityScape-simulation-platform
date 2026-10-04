"""Unit tests for VehicleOrderingService.order_vehicles against fakes (no database)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from cinis.services.vehicle_ordering_service import VehicleOrderingService

D = Decimal
DATE = datetime.date(1880, 2, 1)


@dataclass
class _FakeVehicleType:
    VehicleTypeID: int
    TimberRequiredPerVehicle: Decimal
    StoneRequiredPerVehicle: Decimal


@dataclass
class _FakeCityVehicle:
    CityID: int
    VehicleTypeID: int
    Count: int = 0


class _FakeVehicleRepository:
    def __init__(self, vehicle_type, existing_count=0):
        self._vehicle_type = vehicle_type
        self.vehicle = _FakeCityVehicle(CityID=1, VehicleTypeID=vehicle_type.VehicleTypeID, Count=existing_count)
        self.create_calls = 0

    def get_vehicle_type(self, code):
        return self._vehicle_type

    def get_or_create_city_vehicle(self, city_id, vehicle_type_id):
        self.create_calls += 1
        return self.vehicle


class _FakeInventoryService:
    def __init__(self):
        self.entries = []

    def get_resource_id(self, code):
        return {"R-004": 4, "R-003": 3}[code]

    def record_ledger_entry(self, **kwargs):
        self.entries.append(kwargs)


def _build(timber=D("50"), stone=D("0"), existing_count=0):
    vt = _FakeVehicleType(VehicleTypeID=1, TimberRequiredPerVehicle=timber, StoneRequiredPerVehicle=stone)
    repo = _FakeVehicleRepository(vt, existing_count)
    inventory = _FakeInventoryService()
    return VehicleOrderingService(repo, inventory), repo, inventory


def test_orders_a_boat_matching_the_real_catalog_timber_only():
    service, repo, inventory = _build(timber=D("50"), stone=D("0"))

    result = service.order_vehicles(1, "V-001", 1, DATE)

    assert len(inventory.entries) == 1  # stone skipped (zero)
    assert inventory.entries[0]["amount"] == D("-50")
    assert inventory.entries[0]["resource_id"] == 4
    assert result.Count == 1


def test_quantities_scale_and_both_materials_write_when_both_nonzero():
    service, repo, inventory = _build(timber=D("10"), stone=D("5"))
    service.order_vehicles(1, "V-001", 3, DATE)
    assert inventory.entries[0]["amount"] == D("-30")  # timber
    assert inventory.entries[1]["amount"] == D("-15")  # stone


def test_count_accumulates_on_an_existing_vehicle_row():
    service, repo, _ = _build(existing_count=2)
    result = service.order_vehicles(1, "V-001", 3, DATE)
    assert result.Count == 5


def test_vehicles_ordered_below_one_raises_before_anything_is_staged():
    service, repo, inventory = _build()
    with pytest.raises(ValueError, match="at least 1"):
        service.order_vehicles(1, "V-001", 0, DATE)
    assert inventory.entries == [] and repo.create_calls == 0


def test_trace_ids_are_forwarded_to_material_writes():
    service, *_ , inventory = _build(timber=D("10"), stone=D("5"))
    service.order_vehicles(1, "V-001", 1, DATE, simulation_run_id=7, simulation_tick_id=3)
    assert all(e["simulation_run_id"] == 7 and e["simulation_tick_id"] == 3 for e in inventory.entries)
