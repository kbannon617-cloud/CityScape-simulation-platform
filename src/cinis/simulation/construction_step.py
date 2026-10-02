"""
The Construction tick step (ADR-0011; runs only on a month-boundary tick,
per ADR-0009 Decision 1, alongside Population Aging and Production).

Placement: after Production, before NeedsConsumption - the same slot
Production already occupies relative to Needs, extended by one step.
Construction does not compete with FOOD/HEATING resources (it consumes
Timber/Stone, deducted already at order time - see ConstructionService),
so this step's exact position relative to Production has no material
consequence. Flagged here for the same reason ADR-0011/steps.py flags the
Aging-before-Production ordering: nothing about it was pinned down
elsewhere, so it's a judgment call, not a silent assumption.

Logs a ConstructionCompleted event for every project that finishes this
tick (see events/event_types.py - not required by ADR-0011 itself, added
to match the NeedsShortfall precedent from needs_step.py and Document 7's
explainability requirement).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cinis.events.event_types import CONSTRUCTION_COMPLETED
from cinis.models.construction import STATUS_COMPLETE
from cinis.repositories.city_repository import CityRepository
from cinis.repositories.construction_repository import ConstructionRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.construction_service import ConstructionService
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService
from cinis.simulation.tick import StepCadence, TickContext, TickStep

STEP_NAME = "Construction"


@dataclass(frozen=True)
class ConstructionStepDependencies:
    city_id: int
    construction_service: ConstructionService
    production_repository: ProductionRepository
    run_repository: SimulationRunRepository


def build_construction_step_dependencies(session: Session) -> ConstructionStepDependencies:
    """Wire the real repositories and service onto the tick's session."""
    production_repository = ProductionRepository(session)
    return ConstructionStepDependencies(
        city_id=CityRepository(session).get_primary_active_city().CityID,
        construction_service=ConstructionService(
            ConstructionRepository(session),
            TreasuryService(TreasuryRepository(session)),
            InventoryService(InventoryRepository(session)),
            production_repository,
            PopulationRepository(session),
        ),
        production_repository=production_repository,
        run_repository=SimulationRunRepository(session),
    )


def make_construction_step(
    dependencies_factory: Callable[
        [Session], ConstructionStepDependencies
    ] = build_construction_step_dependencies,
) -> TickStep:
    """Build the step. dependencies_factory exists so unit tests can supply
    fakes; production code uses the default.

    Only advances existing projects (advance_projects). Ordering a new
    project (order_project) is a command triggered on demand, never
    called automatically from a tick - see ConstructionService's
    docstring.
    """

    def execute(context: TickContext) -> None:
        deps = dependencies_factory(context.session)

        touched_projects = deps.construction_service.advance_projects(
            city_id=deps.city_id,
            tick_date=context.simulation_date,
        )

        # advance_projects returns every project it touched this tick,
        # completed or not (ConstructionService docstring); only the
        # completed ones get a ConstructionCompleted event.
        for project in touched_projects:
            if project.Status != STATUS_COMPLETE:
                continue
            building_type = deps.production_repository.get_building_type_by_id(
                project.BuildingTypeID
            )
            deps.run_repository.add_event(
                simulation_run_id=context.simulation_run_id,
                simulation_tick_id=context.simulation_tick_id,
                simulation_date=context.simulation_date,
                event_type=CONSTRUCTION_COMPLETED,
                city_id=deps.city_id,
                description=f"{project.BuildingsOrdered}x {building_type.Code} completed.",
                payload={
                    "ConstructionProjectID": project.ConstructionProjectID,
                    "BuildingTypeCode": building_type.Code,
                    "BuildingsOrdered": project.BuildingsOrdered,
                },
            )

    return TickStep(name=STEP_NAME, execute=execute, cadence=StepCadence.MONTH_BOUNDARY)
