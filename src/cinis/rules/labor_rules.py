"""
Labor capability rules: pure calculation, no database access. Models
AVAILABLE labor capacity only - allocating that capacity to industries
requires the Economy/Production domain (Milestone 3+) and is out of
scope here, per ADR-0005.
"""

from __future__ import annotations

import math


def calculate_available_labor(adult_count: int, participation_rate_percent: float) -> int:
    """Return how many adults are available as labor capacity.

    Floor, for the same determinism reasons as calculate_aged_count: no
    random rounding, never "creates" a worker from a rounded-up fraction.
    """
    if adult_count < 0:
        raise ValueError(f"adult_count must be non-negative, got {adult_count}")
    if participation_rate_percent < 0:
        raise ValueError(
            f"participation_rate_percent must be non-negative, got {participation_rate_percent}"
        )

    return math.floor(adult_count * participation_rate_percent / 100)
