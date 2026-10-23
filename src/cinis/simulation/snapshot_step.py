"""
The Snapshot tick step (Step 4.7, SNAPSHOTS leg of CURRENT STATE +
EVENTS + SNAPSHOTS). Runs on month-boundary cadence, same bucket as
Aging/Production/Construction (Document 2: "snapshot frequency can vary
by entity" - monthly matches the cadence those already use, no new one
introduced).

Last in the step list: captures state AFTER every other step for this
tick has run, consistent with the Master Prompt's canonical cycle, which
ends with "Validation & Persistence: ... commit tick snapshot/history."

Payload keys (all point-in-time, each already authoritatively tracked
elsewhere - this step is a read-optimized rollup, not a new source of
truth): AdultCount, ChildCount, TreasuryBalance, Inventory (dict of
resource code -> quantity, limited to the resources Needs/Construction
care about - Wheat, Trout, Timber, Stone), Buildings (dict of building
type code -> count), Vehicles (dict of vehicle type code -> count).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.repositories.city_repository import CityRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.repositories.snapshot_repository import SnapshotRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.repositories.vehicle_repository import VehicleRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.treasury_service import TreasuryService
from cinis.simulation.tick import StepCadence, TickContext, TickStep

STEP_NAME = "Snapshot"

TRACKED_RESOURCE_CODES = ("R-001", "R-002", "R-003", "R-004")


@dataclass(frozen=True)
class SnapshotStepDependencies:
    city_id: int
    population_repository: PopulationRepository
    treasury_service: TreasuryService
    inventory_service: InventoryService
    production_repository: ProductionRepository
    vehicle_repository: VehicleRepository
    snapshot_repository: SnapshotRepository


def build_snapshot_step_dependencies(session: Session) -> SnapshotStepDependencies:
    """Wire the real repositories and services onto the tick's session."""
    return SnapshotStepDependencies(
        city_id=CityRepository(session).get_primary_active_city().CityID,
        population_repository=PopulationRepository(session),
        treasury_service=TreasuryService(TreasuryRepository(session)),
        inventory_service=InventoryService(InventoryRepository(session)),
        production_repository=ProductionRepository(session),
        vehicle_repository=VehicleRepository(session),
        snapshot_repository=SnapshotRepository(session),
    )


def _decimal_to_str(value: Decimal) -> str:
    """JSON has no Decimal type; store the exact string (determinism -
    matches SimulationRunRepository.serialize_payload's own convention)."""
    return str(value)


def make_snapshot_step(
    dependencies_factory: Callable[
        [Session], SnapshotStepDependencies
    ] = build_snapshot_step_dependencies,
) -> TickStep:
    """Build the step. dependencies_factory exists so unit tests can supply
    fakes; production code uses the default."""

    def execute(context: TickContext) -> None:
        deps = dependencies_factory(context.session)

        adult = deps.population_repository.get_group(deps.city_id, "ADULT")
        child = deps.population_repository.get_group(deps.city_id, "CHILD")
        inventory = {
            code: _decimal_to_str(deps.inventory_service.get_quantity(deps.city_id, code))
            for code in TRACKED_RESOURCE_CODES
        }

        deps.snapshot_repository.record_snapshot(
            simulation_run_id=context.simulation_run_id,
            simulation_tick_id=context.simulation_tick_id,
            simulation_date=context.simulation_date,
            city_id=deps.city_id,
            payload={
                "AdultCount": adult.Count,
                "ChildCount": child.Count,
                "TreasuryBalance": _decimal_to_str(deps.treasury_service.get_balance(deps.city_id)),
                "Inventory": inventory,
                "Buildings": deps.production_repository.get_city_buildings(deps.city_id),
                "Vehicles": deps.vehicle_repository.get_city_vehicles(deps.city_id),
            },
        )

    return TickStep(name=STEP_NAME, execute=execute, cadence=StepCadence.MONTH_BOUNDARY)
