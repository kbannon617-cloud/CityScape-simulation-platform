"""
Production rules: pure calculations with no database access.
"""

from __future__ import annotations


def calculate_staffed_building_count(
    total_count: int, workers_per_building: int, available_labor: int
) -> int:
    """Return how many of a city's buildings of one type can actually be
    staffed this month, given a shared labor pool.

    Buildings needing zero workers per building are never labor-limited.
    Otherwise, floor(available_labor / workers_per_building), capped at
    total_count - deterministic, no partial-worker fractions.
    """
    if total_count < 0:
        raise ValueError(f"total_count must be non-negative, got {total_count}")
    if workers_per_building < 0:
        raise ValueError(f"workers_per_building must be non-negative, got {workers_per_building}")
    if available_labor < 0:
        raise ValueError(f"available_labor must be non-negative, got {available_labor}")

    if workers_per_building == 0:
        return total_count

    max_staffable = available_labor // workers_per_building
    return min(total_count, max_staffable)
