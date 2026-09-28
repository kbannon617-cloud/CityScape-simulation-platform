"""
Construction duration rules: pure arithmetic, no database access.

Mirrors the design-concept workbook's Construction Projects sheet
(columns M, O, P) with one change per ADR-0011: everything here is
computed once, at order time, from the ScenarioParameter rates and the
completed-Construction-Crew count at that moment - never recalculated
later even if rates or the crew count change.
"""

from __future__ import annotations

import math
from decimal import Decimal


def compute_base_duration_months(total_cost: Decimal, monthly_budget: Decimal) -> int:
    """Base duration before any speed bonus, in whole months.

    A free order (total_cost <= 0, e.g. Construction Crew's zero
    ConstructionCost) still takes at least 1 month, matching the
    workbook's IF(Cost=0, 1, ...). Otherwise, ceiling(cost / budget),
    floored at 1 month.
    """
    if monthly_budget <= 0:
        raise ValueError(f"monthly_budget must be positive, got {monthly_budget}")
    if total_cost <= 0:
        return 1
    return max(1, math.ceil(total_cost / monthly_budget))


def compute_speed_bonus(completed_crew_count: int, bonus_per_crew: Decimal) -> Decimal:
    """The fractional speed bonus from completed Construction Crew
    buildings at order time. Uncapped, per the workbook."""
    if completed_crew_count < 0:
        raise ValueError(f"completed_crew_count must be non-negative, got {completed_crew_count}")
    return Decimal(completed_crew_count) * bonus_per_crew


def compute_adjusted_duration_months(base_duration_months: int, speed_bonus: Decimal) -> int:
    """Base duration shortened by the speed bonus, floored at 1 month."""
    if base_duration_months < 1:
        raise ValueError(f"base_duration_months must be at least 1, got {base_duration_months}")
    if speed_bonus < 0:
        raise ValueError(f"speed_bonus must be non-negative, got {speed_bonus}")
    adjusted = Decimal(base_duration_months) / (Decimal(1) + speed_bonus)
    return max(1, math.ceil(adjusted))
