"""
The Population Aging tick step (Document 6 tick cycle; ADR-0009 Decision
1: runs only on a month-boundary tick).

Runs before the Production step in the same tick, so production sees the
updated labor pool (ADR-0009 Decision 1, explicit).

PopulationService.apply_monthly_aging writes no ledger entries - it only
moves counts between PopulationGroup rows - so there is no run/tick trace
to carry here, unlike the needs and production steps.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cinis.repositories.city_repository import CityRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.services.population_service import PopulationService
from cinis.simulation.tick import StepCadence, TickContext, TickStep

STEP_NAME = "PopulationAging"


@dataclass(frozen=True)
class AgingStepDependencies:
    city_id: int
    population_service: PopulationService


def build_aging_step_dependencies(session: Session) -> AgingStepDependencies:
    """Wire the real repository and service onto the tick's session."""
    return AgingStepDependencies(
        city_id=CityRepository(session).get_primary_active_city().CityID,
        population_service=PopulationService(PopulationRepository(session)),
    )


def make_aging_step(
    dependencies_factory: Callable[[Session], AgingStepDependencies] = build_aging_step_dependencies,
) -> TickStep:
    """Build the step. dependencies_factory exists so unit tests can supply
    fakes; production code uses the default."""

    def execute(context: TickContext) -> None:
        deps = dependencies_factory(context.session)
        deps.population_service.apply_monthly_aging(deps.city_id, context.scenario_id)

    return TickStep(name=STEP_NAME, execute=execute, cadence=StepCadence.MONTH_BOUNDARY)
