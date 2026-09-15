"""
Production service: executes one month of production for a city.

Orchestrates three existing pieces rather than duplicating their logic:
- PopulationService.calculate_available_labor (M2) for the shared labor
  pool
- ProductionRepository for the building/flow catalog
- InventoryService (M3 Step 3) for every actual inventory change

Two design decisions worth stating explicitly, since neither is dictated
by the data alone:

1. Labor allocation is first-come-first-served, processed in
   BuildingType.Code order, depleting a shared labor pool as it goes. No
   priority system exists yet - that is real, not-yet-built M4+ work, not
   invented here.
2. Input shortages are all-or-nothing per building type: if a building
   cannot get 100% of a required input, it produces nothing that month,
   rather than partially producing. This is a real simplification, not
   an oversight - there is no source data suggesting how partial
   fulfillment should behave.

Standalone and callable now, ahead of any tick engine - Milestone 4's
SimulationEngine will call this once it exists.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.rules.production_rules import calculate_staffed_building_count
from cinis.services.inventory_service import InsufficientInventoryError, InventoryService
from cinis.services.population_service import PopulationService


@dataclass(frozen=True)
class ProductionResult:
    building_type_code: str
    owned_count: int
    staffed_count: int
    workers_used: int
    inputs_consumed: dict[str, Decimal] = field(default_factory=dict)
    outputs_produced: dict[str, Decimal] = field(default_factory=dict)
    skipped_reason: str | None = None


class ProductionService:
    def __init__(
        self,
        production_repository: ProductionRepository,
        inventory_service: InventoryService,
        population_repository: PopulationRepository,
    ):
        self._production_repository = production_repository
        self._inventory_service = inventory_service
        self._population_service = PopulationService(population_repository)

    def execute_monthly_production(
        self, city_id: int, scenario_id: int, entry_date: datetime.date
    ) -> list[ProductionResult]:
        available_labor = self._population_service.calculate_available_labor(
            city_id, scenario_id
        )
        buildings = self._production_repository.get_city_buildings_with_type(city_id)

        results: list[ProductionResult] = []

        for building, building_type in buildings:
            staffed_count = calculate_staffed_building_count(
                total_count=building.Count,
                workers_per_building=building_type.WorkersPerBuilding,
                available_labor=available_labor,
            )

            if staffed_count <= 0:
                results.append(
                    ProductionResult(
                        building_type_code=building_type.Code,
                        owned_count=building.Count,
                        staffed_count=0,
                        workers_used=0,
                        skipped_reason="No labor available",
                    )
                )
                continue

            workers_used = staffed_count * building_type.WorkersPerBuilding
            flows = self._production_repository.get_flows_for_building_type(building_type.Code)
            input_flows = [f for f in flows if f.FlowType == "Input"]
            output_flows = [f for f in flows if f.FlowType == "Output"]

            planned_inputs = {
                flow.resource.Code: flow.UnitsPerBuildingPerMonth * staffed_count
                for flow in input_flows
            }

            insufficient = any(
                self._inventory_service.get_quantity(city_id, code) < needed
                for code, needed in planned_inputs.items()
            )

            if insufficient:
                available_labor -= workers_used  # labor is still spent even if idle
                results.append(
                    ProductionResult(
                        building_type_code=building_type.Code,
                        owned_count=building.Count,
                        staffed_count=staffed_count,
                        workers_used=workers_used,
                        skipped_reason="Insufficient input inventory",
                    )
                )
                continue

            inputs_consumed: dict[str, Decimal] = {}
            for flow in input_flows:
                amount = flow.UnitsPerBuildingPerMonth * staffed_count
                try:
                    self._inventory_service.record_ledger_entry(
                        city_id=city_id,
                        resource_id=flow.ResourceID,
                        amount=-amount,
                        entry_date=entry_date,
                        notes=f"Consumed by {building_type.Code}",
                    )
                except InsufficientInventoryError:
                    # Should not happen given the pre-check above, but
                    # never leave a building half-consumed if it does.
                    raise
                inputs_consumed[flow.resource.Code] = amount

            outputs_produced: dict[str, Decimal] = {}
            for flow in output_flows:
                amount = flow.UnitsPerBuildingPerMonth * staffed_count
                self._inventory_service.record_ledger_entry(
                    city_id=city_id,
                    resource_id=flow.ResourceID,
                    amount=amount,
                    entry_date=entry_date,
                    notes=f"Produced by {building_type.Code}",
                )
                outputs_produced[flow.resource.Code] = amount

            available_labor -= workers_used

            results.append(
                ProductionResult(
                    building_type_code=building_type.Code,
                    owned_count=building.Count,
                    staffed_count=staffed_count,
                    workers_used=workers_used,
                    inputs_consumed=inputs_consumed,
                    outputs_produced=outputs_produced,
                    skipped_reason=None,
                )
            )

        return results
