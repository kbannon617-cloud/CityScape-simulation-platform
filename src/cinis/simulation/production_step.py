"""
The Production tick step (Document 6 tick cycle; ADR-0009 Decision 1: runs
only on a month-boundary tick, after Population Aging).

Runs before the Needs & Consumption step in the same tick (Document 6's
canonical order: Population/Labor, then Production, then Inventory
Ingestion, then Needs & Consumption), so newly produced output is on hand
before that day's consumption runs. See simulation/steps.py for where this
ordering is assembled and flagged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cinis.repositories.city_repository import CityRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.production_service import ProductionService
from cinis.simulation.tick import StepCadence, TickContext, TickStep

STEP_NAME = "Production"


@dataclass(frozen=True)
class ProductionStepDependencies:
    city_id: int
    production_service: ProductionService


def build_production_step_dependencies(session: Session) -> ProductionStepDependencies:
    """Wire the real repositories and service onto the tick's session."""
    return ProductionStepDependencies(
        city_id=CityRepository(session).get_primary_active_city().CityID,
        production_service=ProductionService(
            ProductionRepository(session),
            InventoryService(InventoryRepository(session)),
            PopulationRepository(session),
        ),
    )


def make_production_step(
    dependencies_factory: Callable[
        [Session], ProductionStepDependencies
    ] = build_production_step_dependencies,
) -> TickStep:
    """Build the step. dependencies_factory exists so unit tests can supply
    fakes; production code uses the default."""

    def execute(context: TickContext) -> None:
        deps = dependencies_factory(context.session)
        deps.production_service.execute_monthly_production(
            city_id=deps.city_id,
            scenario_id=context.scenario_id,
            entry_date=context.simulation_date,
            simulation_run_id=context.simulation_run_id,
            simulation_tick_id=context.simulation_tick_id,
        )

    return TickStep(name=STEP_NAME, execute=execute, cadence=StepCadence.MONTH_BOUNDARY)
