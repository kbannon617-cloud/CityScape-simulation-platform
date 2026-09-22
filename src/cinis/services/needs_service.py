"""
Needs service: computes total citywide daily consumption per need
category, given current population counts and seeded consumption rates.

Scope boundary (ADR-0005): this computes what the city NEEDS. It does not
deplete any inventory or check whether the city HAS enough - that
requires the Economy/Inventory domain (Milestone 3+).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cinis.repositories.needs_repository import NeedsRepository
from cinis.repositories.population_repository import PopulationRepository


@dataclass(frozen=True)
class NeedTotal:
    need_type_code: str
    total_quantity: float
    unit_code: str


@dataclass(frozen=True)
class ExactNeedTotal:
    """Same as NeedTotal but with an exact Decimal quantity, for callers
    that write quantities to a ledger (the float form can carry binary
    noise, e.g. 87.99999999999999 for a true 88)."""

    need_type_code: str
    total_quantity: Decimal
    unit_code: str


class NeedsService:
    def __init__(self, needs_repository: NeedsRepository, population_repository: PopulationRepository):
        self._needs_repository = needs_repository
        self._population_repository = population_repository

    def calculate_daily_need_totals(self, city_id: int) -> list[NeedTotal]:
        """Return total daily consumption per need type for a city.

        For each (group type, need type) consumption rate, multiplies by
        that group's current population count and sums across group types
        that share the same need type and unit.
        """
        return [
            NeedTotal(
                need_type_code=total.need_type_code,
                total_quantity=float(total.total_quantity),
                unit_code=total.unit_code,
            )
            for total in self.calculate_daily_need_totals_exact(city_id)
        ]

    def calculate_daily_need_totals_exact(self, city_id: int) -> list[ExactNeedTotal]:
        """Same calculation as calculate_daily_need_totals, in exact Decimal
        arithmetic.

        Rates are stored as DECIMAL(10,4) but the repository hands them
        over as floats. A float with at most 15 significant digits
        round-trips exactly through its shortest string form, so converting
        each RATE with Decimal(str(rate)) recovers the stored value; the
        multiplication by the integer head-count and the sums are then
        exact.
        """
        population_by_group = self._population_repository.get_population_by_city(city_id)
        rates = self._needs_repository.get_consumption_rates()

        totals: dict[tuple[str, str], Decimal] = {}
        for group_code, need_code, quantity_per_person, unit_code in rates:
            group_count = population_by_group.get(group_code, 0)
            key = (need_code, unit_code)
            totals[key] = totals.get(key, Decimal("0")) + (
                Decimal(str(quantity_per_person)) * group_count
            )

        return [
            ExactNeedTotal(need_type_code=need_code, total_quantity=total, unit_code=unit_code)
            for (need_code, unit_code), total in totals.items()
        ]
