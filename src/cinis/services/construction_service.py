"""
Construction service: orders new building projects.

order_project() is a command, called on demand (e.g. by a future
UI/API), NOT automatically every tick - unlike Production or Needs, a
project only exists because someone chose to order it. Advancing an
in-progress project's MonthsElapsed and completing it (adding to
Building.Count) is Step 4.5c's tick step, in a separate service.

Per ADR-0011:
  - Cost and materials are deducted immediately, at order time, through
    the existing TreasuryService/InventoryService - so insufficient
    funds or materials fail exactly the way they already do elsewhere
    (InventoryService raises InsufficientInventoryError; TreasuryService
    currently allows a negative balance, an existing M3 behavior this
    service does not change - see ADR-0011 delivery notes).
  - AdjustedDurationMonths is computed once, from the current
    ScenarioParameter rates and the current completed-Construction-Crew
    count, and never recalculated later.
  - The concurrent-project limit (MaxActiveConstructionProjectsPerCity)
    is a ScenarioParameter, not a database constraint, because it is
    expected to be raised above 1 in the future.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from cinis.models.construction import ConstructionProject
from cinis.repositories.construction_repository import ConstructionRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.rules.construction_rules import (
    compute_adjusted_duration_months,
    compute_base_duration_months,
    compute_speed_bonus,
)
from cinis.rules.ledger_rules import validate_ledger_trace
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService

CONSTRUCTION_CREW_CODE = "B-007"
TIMBER_RESOURCE_CODE = "R-004"
STONE_RESOURCE_CODE = "R-003"
CONSTRUCTION_COST_CATEGORY = "CONSTRUCTION_COST"

PARAM_MAX_ACTIVE_PROJECTS = "MaxActiveConstructionProjectsPerCity"
PARAM_MONTHLY_BUDGET = "MonthlyConstructionBudget"
PARAM_BONUS_PER_CREW = "ConstructionBonusPerCompletedCrew"


class MaxActiveConstructionProjectsExceededError(RuntimeError):
    """Raised when ordering would exceed the scenario's concurrent-project
    limit for this city."""


class ConstructionService:
    def __init__(
        self,
        repository: ConstructionRepository,
        treasury_service: TreasuryService,
        inventory_service: InventoryService,
        production_repository: ProductionRepository,
        population_repository: PopulationRepository,
    ):
        self._repository = repository
        self._treasury_service = treasury_service
        self._inventory_service = inventory_service
        self._production_repository = production_repository
        self._population_repository = population_repository

    def order_project(
        self,
        city_id: int,
        scenario_id: int,
        building_type_code: str,
        buildings_ordered: int,
        order_date: datetime.date,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> ConstructionProject:
        """Order buildings_ordered buildings of building_type_code for
        city_id. Deducts cost/materials immediately and creates an
        InProgress ConstructionProject.

        simulation_run_id and simulation_tick_id (ADR-0009 Decision 3) are
        supplied together by the tick engine, or both omitted; a ValueError
        is raised before anything is staged if only one is given.

        Raises MaxActiveConstructionProjectsExceededError if the city is
        already at its concurrent-project limit, InsufficientInventoryError
        if Timber or Stone would go negative. Nothing is staged before
        these checks run.
        """
        if buildings_ordered < 1:
            raise ValueError(f"buildings_ordered must be at least 1, got {buildings_ordered}")
        validate_ledger_trace(simulation_run_id, simulation_tick_id)

        max_active_projects = int(
            self._population_repository.get_scenario_parameter(
                scenario_id, PARAM_MAX_ACTIVE_PROJECTS
            )
        )
        active_count = self._repository.count_active_projects(city_id)
        if active_count >= max_active_projects:
            raise MaxActiveConstructionProjectsExceededError(
                f"CityID={city_id} already has {active_count} active project(s); "
                f"the scenario limit is {max_active_projects}."
            )

        building_type = self._production_repository.get_building_type(building_type_code)
        quantity = Decimal(buildings_ordered)
        total_cost = building_type.ConstructionCost * quantity
        total_timber = building_type.TimberRequiredPerBuilding * quantity
        total_stone = building_type.StoneRequiredPerBuilding * quantity

        monthly_budget = Decimal(
            str(self._population_repository.get_scenario_parameter(scenario_id, PARAM_MONTHLY_BUDGET))
        )
        bonus_per_crew = Decimal(
            str(self._population_repository.get_scenario_parameter(scenario_id, PARAM_BONUS_PER_CREW))
        )
        completed_crews = self._production_repository.get_city_buildings(city_id).get(
            CONSTRUCTION_CREW_CODE, 0
        )

        base_duration = compute_base_duration_months(total_cost, monthly_budget)
        speed_bonus = compute_speed_bonus(completed_crews, bonus_per_crew)
        adjusted_duration = compute_adjusted_duration_months(base_duration, speed_bonus)

        # Materials first: InsufficientInventoryError must abort before the
        # treasury is touched, so a failed order leaves nothing staged that
        # would need separate unwinding (the caller's session is never
        # partially committed either way, but this keeps the staged state
        # easy to reason about).
        if total_timber > 0:
            self._inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=self._inventory_service.get_resource_id(TIMBER_RESOURCE_CODE),
                amount=-total_timber,
                entry_date=order_date,
                notes=f"Construction order: {buildings_ordered}x {building_type_code}.",
                simulation_run_id=simulation_run_id,
                simulation_tick_id=simulation_tick_id,
            )
        if total_stone > 0:
            self._inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=self._inventory_service.get_resource_id(STONE_RESOURCE_CODE),
                amount=-total_stone,
                entry_date=order_date,
                notes=f"Construction order: {buildings_ordered}x {building_type_code}.",
                simulation_run_id=simulation_run_id,
                simulation_tick_id=simulation_tick_id,
            )
        if total_cost > 0:
            self._treasury_service.record_ledger_entry(
                city_id=city_id,
                category_code=CONSTRUCTION_COST_CATEGORY,
                amount=-total_cost,
                entry_date=order_date,
                simulation_run_id=simulation_run_id,
                simulation_tick_id=simulation_tick_id,
            )

        return self._repository.create_project(
            city_id=city_id,
            building_type_id=building_type.BuildingTypeID,
            buildings_ordered=buildings_ordered,
            order_date=order_date,
            total_construction_cost=total_cost,
            total_timber_required=total_timber,
            total_stone_required=total_stone,
            adjusted_duration_months=adjusted_duration,
        )
