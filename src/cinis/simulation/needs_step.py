"""
The Needs & Consumption tick step (Document 6 tick cycle; ADR-0009
Decision 1: runs every tick).

Consumes the primary active city's daily needs through
NeedsConsumptionService and records a NeedsShortfall event for every need
that could not be fully met (ADR-0009 Decision 2). A shortfall never fails
the tick.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cinis.events.event_types import NEEDS_SHORTFALL
from cinis.repositories.city_repository import CityRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.need_resource_repository import NeedResourceRepository
from cinis.repositories.needs_repository import NeedsRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.needs_consumption_service import NeedsConsumptionService
from cinis.services.needs_service import NeedsService
from cinis.simulation.tick import StepCadence, TickContext, TickStep

STEP_NAME = "NeedsConsumption"


@dataclass(frozen=True)
class NeedsStepDependencies:
    city_id: int
    consumption_service: NeedsConsumptionService
    run_repository: SimulationRunRepository


def build_needs_step_dependencies(session: Session) -> NeedsStepDependencies:
    """Wire the real repositories and services onto the tick's session."""
    return NeedsStepDependencies(
        city_id=CityRepository(session).get_primary_active_city().CityID,
        consumption_service=NeedsConsumptionService(
            NeedsService(NeedsRepository(session), PopulationRepository(session)),
            NeedResourceRepository(session),
            InventoryService(InventoryRepository(session)),
        ),
        run_repository=SimulationRunRepository(session),
    )


def make_needs_consumption_step(
    dependencies_factory: Callable[[Session], NeedsStepDependencies] = build_needs_step_dependencies,
) -> TickStep:
    """Build the step. dependencies_factory exists so unit tests can supply
    fakes; production code uses the default."""

    def execute(context: TickContext) -> None:
        deps = dependencies_factory(context.session)

        results = deps.consumption_service.consume_daily_needs(
            city_id=deps.city_id,
            entry_date=context.simulation_date,
            simulation_run_id=context.simulation_run_id,
            simulation_tick_id=context.simulation_tick_id,
        )

        for result in results:
            if result.shortfall <= 0:
                continue
            deps.run_repository.add_event(
                simulation_run_id=context.simulation_run_id,
                simulation_tick_id=context.simulation_tick_id,
                simulation_date=context.simulation_date,
                event_type=NEEDS_SHORTFALL,
                city_id=deps.city_id,
                description=f"{result.need_type_code} need not fully met.",
                payload={
                    "NeedTypeCode": result.need_type_code,
                    "Needed": result.needed,
                    "Consumed": result.consumed,
                    "Shortfall": result.shortfall,
                },
            )

    return TickStep(name=STEP_NAME, execute=execute, cadence=StepCadence.EVERY_TICK)
