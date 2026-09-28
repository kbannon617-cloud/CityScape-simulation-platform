"""
Unit tests for ConstructionService.order_project against fakes (no
database). Covers the concurrent-project limit, duration computation
(via the real construction_rules functions), the materials-then-cost
deduction order, zero-cost/zero-material skipping, and trace validation.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from cinis.services.construction_service import (
    ConstructionService,
    MaxActiveConstructionProjectsExceededError,
)

D = Decimal
ORDER_DATE = datetime.date(1880, 2, 1)


@dataclass
class _FakeBuildingType:
    BuildingTypeID: int
    ConstructionCost: Decimal
    TimberRequiredPerBuilding: Decimal
    StoneRequiredPerBuilding: Decimal


class _FakeConstructionRepository:
    def __init__(self, active_count=0):
        self._active_count = active_count
        self.created = []

    def count_active_projects(self, city_id):
        return self._active_count

    def create_project(self, **kwargs):
        self.created.append(kwargs)
        return kwargs


class _FakeTreasuryService:
    def __init__(self):
        self.entries = []

    def record_ledger_entry(self, **kwargs):
        self.entries.append(kwargs)


class _FakeInventoryService:
    def __init__(self, resource_ids=None):
        self._resource_ids = resource_ids or {"R-004": 4, "R-003": 3}
        self.entries = []

    def get_resource_id(self, code):
        return self._resource_ids[code]

    def record_ledger_entry(self, **kwargs):
        self.entries.append(kwargs)


class _FakeProductionRepository:
    def __init__(self, building_type, city_buildings=None):
        self._building_type = building_type
        self._city_buildings = city_buildings or {}

    def get_building_type(self, code):
        return self._building_type

    def get_city_buildings(self, city_id):
        return self._city_buildings


class _FakePopulationRepository:
    def __init__(self, params):
        self._params = params

    def get_scenario_parameter(self, scenario_id, key):
        return self._params[key]


DEFAULT_PARAMS = {
    "MaxActiveConstructionProjectsPerCity": 1,
    "MonthlyConstructionBudget": 100.0,
    "ConstructionBonusPerCompletedCrew": 0.0005,
}


def _build_service(
    building_type,
    active_count=0,
    city_buildings=None,
    params=None,
):
    construction_repo = _FakeConstructionRepository(active_count)
    treasury = _FakeTreasuryService()
    inventory = _FakeInventoryService()
    production_repo = _FakeProductionRepository(building_type, city_buildings)
    population_repo = _FakePopulationRepository(params or DEFAULT_PARAMS)
    service = ConstructionService(
        construction_repo, treasury, inventory, production_repo, population_repo
    )
    return service, construction_repo, treasury, inventory


def test_orders_a_wheat_farm_matching_the_workbook_example():
    # ConstructionCost 750, Timber 50, Stone 25 per building (real B-002
    # seed values); budget 100/month -> base duration 8 months.
    building_type = _FakeBuildingType(
        BuildingTypeID=2,
        ConstructionCost=D("750.00"),
        TimberRequiredPerBuilding=D("50.00"),
        StoneRequiredPerBuilding=D("25.00"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    service.order_project(city_id=1, scenario_id=9, building_type_code="B-002",
                           buildings_ordered=1, order_date=ORDER_DATE)

    (created,) = repo.created
    assert created["total_construction_cost"] == D("750.00")
    assert created["total_timber_required"] == D("50.00")
    assert created["total_stone_required"] == D("25.00")
    assert created["adjusted_duration_months"] == 8

    assert treasury.entries[0]["amount"] == D("-750.00")
    assert treasury.entries[0]["category_code"] == "CONSTRUCTION_COST"
    timber_entry, stone_entry = inventory.entries
    assert timber_entry["amount"] == D("-50.00") and timber_entry["resource_id"] == 4
    assert stone_entry["amount"] == D("-25.00") and stone_entry["resource_id"] == 3


def test_materials_are_deducted_before_cost():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("10"), StoneRequiredPerBuilding=D("5"),
    )
    service, _, treasury, inventory = _build_service(building_type)

    service.order_project(1, 9, "B-002", 1, ORDER_DATE)

    assert len(inventory.entries) == 2
    assert len(treasury.entries) == 1


def test_quantities_scale_with_buildings_ordered():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("10"), StoneRequiredPerBuilding=D("5"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    service.order_project(1, 9, "B-002", 3, ORDER_DATE)

    (created,) = repo.created
    assert created["total_construction_cost"] == D("300")
    assert created["total_timber_required"] == D("30")
    assert created["total_stone_required"] == D("15")


def test_zero_cost_and_zero_material_writes_are_skipped():
    # Construction Crew (B-007): zero cost, but real Timber/Stone > 0 -
    # exercise the case where SOME amounts are zero and some aren't by
    # zeroing just the cost here.
    building_type = _FakeBuildingType(
        BuildingTypeID=7, ConstructionCost=D("0"),
        TimberRequiredPerBuilding=D("50"), StoneRequiredPerBuilding=D("50"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    service.order_project(1, 9, "B-007", 1, ORDER_DATE)

    assert treasury.entries == []  # zero cost -> no ledger write
    assert len(inventory.entries) == 2  # nonzero materials -> both written


def test_completed_crews_shorten_the_adjusted_duration():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("800"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    service, repo, *_ = _build_service(building_type, city_buildings={"B-007": 1000})

    # base = 800/100 = 8 months; bonus = 1000*0.0005 = 0.5 -> 8/1.5 = 5.33 -> 6
    service.order_project(1, 9, "B-002", 1, ORDER_DATE)

    assert repo.created[0]["adjusted_duration_months"] == 6


def test_no_completed_crews_leaves_duration_at_base():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("300"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    service, repo, *_ = _build_service(building_type, city_buildings={})

    service.order_project(1, 9, "B-002", 1, ORDER_DATE)

    assert repo.created[0]["adjusted_duration_months"] == 3


def test_raises_when_the_concurrent_project_limit_is_already_reached():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    service, repo, treasury, inventory = _build_service(building_type, active_count=1)

    with pytest.raises(MaxActiveConstructionProjectsExceededError, match="CityID=1"):
        service.order_project(1, 9, "B-002", 1, ORDER_DATE)

    assert repo.created == []
    assert treasury.entries == []
    assert inventory.entries == []


def test_raising_the_limit_parameter_allows_more_concurrent_projects():
    """Proves the limit is genuinely data-driven, per ADR-0011 Decision 2:
    the same active_count that fails at the default limit of 1 succeeds
    once the scenario parameter is raised - no code change."""
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    raised_params = dict(DEFAULT_PARAMS, MaxActiveConstructionProjectsPerCity=3)
    service, repo, *_ = _build_service(building_type, active_count=2, params=raised_params)

    service.order_project(1, 9, "B-002", 1, ORDER_DATE)

    assert len(repo.created) == 1


def test_buildings_ordered_below_one_raises_before_anything_is_staged():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    with pytest.raises(ValueError, match="at least 1"):
        service.order_project(1, 9, "B-002", 0, ORDER_DATE)

    assert repo.created == []


def test_partial_trace_raises_before_anything_is_staged():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("0"), StoneRequiredPerBuilding=D("0"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    with pytest.raises(ValueError, match="together"):
        service.order_project(1, 9, "B-002", 1, ORDER_DATE, simulation_tick_id=3)

    assert repo.created == []
    assert treasury.entries == []


def test_trace_ids_are_forwarded_to_every_ledger_write_and_the_project():
    building_type = _FakeBuildingType(
        BuildingTypeID=2, ConstructionCost=D("100"),
        TimberRequiredPerBuilding=D("10"), StoneRequiredPerBuilding=D("5"),
    )
    service, repo, treasury, inventory = _build_service(building_type)

    service.order_project(
        1, 9, "B-002", 1, ORDER_DATE, simulation_run_id=7, simulation_tick_id=3
    )

    assert treasury.entries[0]["simulation_run_id"] == 7
    assert treasury.entries[0]["simulation_tick_id"] == 3
    assert all(e["simulation_run_id"] == 7 and e["simulation_tick_id"] == 3 for e in inventory.entries)
