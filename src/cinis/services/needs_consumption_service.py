"""
Needs consumption service: turns a city's daily need totals into inventory
depletion (ADR-0010), closing the gap left when NeedsService was built to
compute needs only (ADR-0005).

For each need type that has a mapping, resources are drained in
consumption-priority order (1 first), each up to its available stock, until
the need is met or the mapped resources run out. Anything unmet is reported
as a shortfall on the result; recording it as an event is the caller's job
(the tick step), so this service stays free of event plumbing.

Rules (ADR-0009 Decision 2, ADR-0010):
  * Need types with no mapping are skipped: no consumption, no result.
  * The need is floored to ledger precision (four decimals).
  * Consumption is applied only through InventoryService, as negative
    ledger entries carrying the run/tick trace the engine supplies.
  * Need types are processed in code order, so results and ledger writes
    are deterministic.

Unit handling is intentionally absent (ADR-0010 Decision 3): a need's
quantity is applied 1:1 against stock in the resource's own unit.

Does not commit; the caller (the engine) owns the transaction boundary.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from cinis.repositories.need_resource_repository import NeedResourceRepository
from cinis.rules.quantity_rules import floor_to_ledger_precision
from cinis.services.inventory_service import InventoryService
from cinis.services.needs_service import NeedsService


@dataclass(frozen=True)
class ResourceConsumption:
    resource_code: str
    quantity: Decimal


@dataclass(frozen=True)
class NeedConsumptionResult:
    need_type_code: str
    needed: Decimal
    consumed: Decimal
    # Only resources actually drawn from (quantity > 0), in priority order.
    consumption_by_resource: tuple[ResourceConsumption, ...]

    @property
    def shortfall(self) -> Decimal:
        return self.needed - self.consumed


class NeedsConsumptionService:
    def __init__(
        self,
        needs_service: NeedsService,
        need_resource_repository: NeedResourceRepository,
        inventory_service: InventoryService,
    ):
        self._needs_service = needs_service
        self._need_resource_repository = need_resource_repository
        self._inventory_service = inventory_service

    def consume_daily_needs(
        self,
        city_id: int,
        entry_date: datetime.date,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> list[NeedConsumptionResult]:
        """Consume one day of needs for a city and return one result per
        mapped need type (in need-type code order)."""
        mapping = self._need_resource_repository.get_resources_by_need_type()
        totals = sorted(
            self._needs_service.calculate_daily_need_totals_exact(city_id),
            key=lambda total: total.need_type_code,
        )

        results: list[NeedConsumptionResult] = []
        for total in totals:
            mapped_resources = mapping.get(total.need_type_code)
            if not mapped_resources:
                continue

            needed = floor_to_ledger_precision(total.total_quantity)
            remaining = needed
            drawn: list[ResourceConsumption] = []

            for mapped in mapped_resources:
                if remaining <= 0:
                    break
                available = self._inventory_service.get_quantity(city_id, mapped.resource_code)
                take = min(remaining, available)
                if take <= 0:
                    continue

                self._inventory_service.record_ledger_entry(
                    city_id=city_id,
                    resource_id=mapped.resource_id,
                    amount=-take,
                    entry_date=entry_date,
                    notes=f"Daily {total.need_type_code} consumption.",
                    simulation_run_id=simulation_run_id,
                    simulation_tick_id=simulation_tick_id,
                )
                remaining -= take
                drawn.append(ResourceConsumption(resource_code=mapped.resource_code, quantity=take))

            results.append(
                NeedConsumptionResult(
                    need_type_code=total.need_type_code,
                    needed=needed,
                    consumed=needed - remaining,
                    consumption_by_resource=tuple(drawn),
                )
            )

        return results
