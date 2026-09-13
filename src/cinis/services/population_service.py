"""
Population service: orchestrates the aging mechanism using
PopulationRepository (persistence) and cinis.rules.population_rules
(pure calculation). Per Document 6's layering, this service does not
contain SQL access or the aging math itself - it wires the two together.

This is intentionally standalone, callable outside of any tick engine:
Milestone 4 (Simulation Core) will call apply_monthly_aging as one step
in the daily tick sequence, but it is fully testable now, ahead of that
engine existing.
"""

from __future__ import annotations

from dataclasses import dataclass

from cinis.repositories.population_repository import PopulationRepository
from cinis.rules.labor_rules import calculate_available_labor
from cinis.rules.population_rules import calculate_aged_count


@dataclass(frozen=True)
class AgingResult:
    aged_count: int
    new_child_count: int
    new_adult_count: int


class PopulationService:
    def __init__(self, repository: PopulationRepository):
        self._repository = repository

    def apply_monthly_aging(self, city_id: int, scenario_id: int) -> AgingResult:
        """Move the appropriate number of children into the adult group
        for one month, per the scenario's configured aging rate.

        Does not commit; the caller (a test, or eventually the M4 tick
        engine) owns the transaction boundary, consistent with
        Document 6's "controlled transaction boundaries" principle.
        """
        child_group = self._repository.get_group(city_id, "CHILD")
        adult_group = self._repository.get_group(city_id, "ADULT")
        rate_percent = self._repository.get_scenario_parameter(
            scenario_id, "ChildToAdultMonthlyAgingRatePercent"
        )

        aged_count = calculate_aged_count(child_group.Count, rate_percent)

        if aged_count > 0:
            child_group.Count -= aged_count
            adult_group.Count += aged_count

        return AgingResult(
            aged_count=aged_count,
            new_child_count=child_group.Count,
            new_adult_count=adult_group.Count,
        )

    def calculate_available_labor(self, city_id: int, scenario_id: int) -> int:
        """Return how many adults are available as labor capacity.

        This models AVAILABLE capacity only - it does not allocate that
        capacity to any industry (Economy/Production domain, Milestone
        3+), per ADR-0005's scope boundary.
        """
        adult_group = self._repository.get_group(city_id, "ADULT")
        participation_rate = self._repository.get_scenario_parameter(
            scenario_id, "AdultLaborParticipationRatePercent"
        )
        return calculate_available_labor(adult_group.Count, participation_rate)
