"""
Unit tests for ProductionService's orchestration logic, using fake
repositories/services rather than a real database. Covers labor limiting
and input-shortage skipping - the two documented design decisions - plus
the happy path.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from cinis.services.production_service import ProductionService


@dataclass
class _FakeBuilding:
    Count: int


@dataclass
class _FakeBuildingType:
    Code: str
    WorkersPerBuilding: int


@dataclass
class _FakeResource:
    Code: str


@dataclass
class _FakeFlow:
    FlowType: str
    UnitsPerBuildingPerMonth: Decimal
    ResourceID: int
    resource: _FakeResource


class _FakeProductionRepository:
    def __init__(self, buildings_with_types, flows_by_code):
        self._buildings_with_types = buildings_with_types
        self._flows_by_code = flows_by_code

    def get_city_buildings_with_type(self, city_id):
        return self._buildings_with_types

    def get_flows_for_building_type(self, code):
        return self._flows_by_code.get(code, [])


class _FakeInventoryService:
    def __init__(self, starting_quantities: dict[str, Decimal]):
        self.quantities = dict(starting_quantities)
        self.entries = []

    def get_quantity(self, city_id, resource_code):
        return self.quantities.get(resource_code, Decimal("0"))

    def record_ledger_entry(self, city_id, resource_id, amount, entry_date, notes=None):
        # resource_id doubles as the code in these fakes for simplicity
        code = resource_id
        self.quantities[code] = self.quantities.get(code, Decimal("0")) + amount
        self.entries.append((code, amount, notes))


class _FakePopulationRepository:
    """Only needs to support what PopulationService.calculate_available_labor
    calls internally."""

    def __init__(self, adult_count: int, participation_rate: float):
        self._adult_count = adult_count
        self._participation_rate = participation_rate

    def get_group(self, city_id, group_type_code):
        @dataclass
        class _Group:
            Count: int

        return _Group(Count=self._adult_count)

    def get_scenario_parameter(self, scenario_id, key):
        return self._participation_rate


def test_full_labor_and_inventory_produces_output():
    buildings = [(_FakeBuilding(Count=1), _FakeBuildingType(Code="B-002", WorkersPerBuilding=5))]
    flows = {
        "B-002": [
            _FakeFlow(
                FlowType="Output",
                UnitsPerBuildingPerMonth=Decimal("100"),
                ResourceID="R-001",
                resource=_FakeResource(Code="R-001"),
            )
        ]
    }
    production_repo = _FakeProductionRepository(buildings, flows)
    inventory_service = _FakeInventoryService({})
    population_repo = _FakePopulationRepository(adult_count=100, participation_rate=100)

    service = ProductionService(production_repo, inventory_service, population_repo)
    results = service.execute_monthly_production(city_id=1, scenario_id=1, entry_date=datetime.date(2026, 1, 1))

    assert len(results) == 1
    result = results[0]
    assert result.staffed_count == 1
    assert result.skipped_reason is None
    assert result.outputs_produced == {"R-001": Decimal("100")}
    assert inventory_service.quantities["R-001"] == Decimal("100")


def test_insufficient_labor_skips_building_with_reason():
    buildings = [(_FakeBuilding(Count=5), _FakeBuildingType(Code="B-002", WorkersPerBuilding=5))]
    production_repo = _FakeProductionRepository(buildings, {})
    inventory_service = _FakeInventoryService({})
    # Zero available labor: participation rate 0%.
    population_repo = _FakePopulationRepository(adult_count=100, participation_rate=0)

    service = ProductionService(production_repo, inventory_service, population_repo)
    results = service.execute_monthly_production(city_id=1, scenario_id=1, entry_date=datetime.date(2026, 1, 1))

    assert results[0].staffed_count == 0
    assert results[0].skipped_reason == "No labor available"


def test_partial_labor_staffs_only_what_it_can_afford():
    buildings = [(_FakeBuilding(Count=5), _FakeBuildingType(Code="B-002", WorkersPerBuilding=5))]
    flows = {
        "B-002": [
            _FakeFlow(
                FlowType="Output",
                UnitsPerBuildingPerMonth=Decimal("100"),
                ResourceID="R-001",
                resource=_FakeResource(Code="R-001"),
            )
        ]
    }
    production_repo = _FakeProductionRepository(buildings, flows)
    inventory_service = _FakeInventoryService({})
    # 12 available labor / 5 per building = 2 staffable, out of 5 owned.
    population_repo = _FakePopulationRepository(adult_count=12, participation_rate=100)

    service = ProductionService(production_repo, inventory_service, population_repo)
    results = service.execute_monthly_production(city_id=1, scenario_id=1, entry_date=datetime.date(2026, 1, 1))

    assert results[0].owned_count == 5
    assert results[0].staffed_count == 2
    assert results[0].outputs_produced == {"R-001": Decimal("200")}  # 100 * 2 staffed


def test_insufficient_input_inventory_skips_building_but_still_spends_labor():
    buildings = [(_FakeBuilding(Count=1), _FakeBuildingType(Code="B-009", WorkersPerBuilding=25))]
    flows = {
        "B-009": [
            _FakeFlow(
                FlowType="Input",
                UnitsPerBuildingPerMonth=Decimal("100"),
                ResourceID="R-004",
                resource=_FakeResource(Code="R-004"),
            ),
            _FakeFlow(
                FlowType="Output",
                UnitsPerBuildingPerMonth=Decimal("50"),
                ResourceID="R-005",
                resource=_FakeResource(Code="R-005"),
            ),
        ]
    }
    production_repo = _FakeProductionRepository(buildings, flows)
    # Only 10 Timber available, but Saw Mill needs 100.
    inventory_service = _FakeInventoryService({"R-004": Decimal("10")})
    population_repo = _FakePopulationRepository(adult_count=100, participation_rate=100)

    service = ProductionService(production_repo, inventory_service, population_repo)
    results = service.execute_monthly_production(city_id=1, scenario_id=1, entry_date=datetime.date(2026, 1, 1))

    result = results[0]
    assert result.skipped_reason == "Insufficient input inventory"
    assert result.staffed_count == 1  # labor was allocated before the input check
    assert result.workers_used == 25
    assert result.inputs_consumed == {}
    assert result.outputs_produced == {}
    # Confirm nothing was actually written to inventory for the skipped building.
    assert inventory_service.quantities["R-004"] == Decimal("10")
    assert "R-005" not in inventory_service.quantities


def test_labor_spent_on_skipped_building_is_unavailable_to_later_buildings():
    buildings = [
        (_FakeBuilding(Count=1), _FakeBuildingType(Code="B-009", WorkersPerBuilding=25)),
        (_FakeBuilding(Count=1), _FakeBuildingType(Code="B-010", WorkersPerBuilding=10)),
    ]
    flows = {
        "B-009": [
            _FakeFlow(
                FlowType="Input",
                UnitsPerBuildingPerMonth=Decimal("100"),
                ResourceID="R-004",
                resource=_FakeResource(Code="R-004"),
            )
        ],
        "B-010": [
            _FakeFlow(
                FlowType="Output",
                UnitsPerBuildingPerMonth=Decimal("80"),
                ResourceID="R-006",
                resource=_FakeResource(Code="R-006"),
            )
        ],
    }
    production_repo = _FakeProductionRepository(buildings, flows)
    inventory_service = _FakeInventoryService({"R-004": Decimal("0")})  # Saw Mill will be skipped
    # Only 25 labor total: exactly enough for Saw Mill (which then gets
    # skipped for lack of input, but its labor is still spent), leaving 0
    # for Oat Farm.
    population_repo = _FakePopulationRepository(adult_count=25, participation_rate=100)

    service = ProductionService(production_repo, inventory_service, population_repo)
    results = service.execute_monthly_production(city_id=1, scenario_id=1, entry_date=datetime.date(2026, 1, 1))

    saw_mill, oat_farm = results
    assert saw_mill.skipped_reason == "Insufficient input inventory"
    assert oat_farm.skipped_reason == "No labor available"
