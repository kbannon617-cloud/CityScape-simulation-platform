"""
Population aging rules: pure calculations with no database access, so the
math itself is testable in isolation from persistence. Called by
PopulationService, which handles the actual reads/writes via
PopulationRepository.
"""

from __future__ import annotations

import math


def calculate_aged_count(child_count: int, rate_percent: float) -> int:
    """Return how many children age into adults this month.

    Uses floor (round toward zero), a deterministic choice consistent with
    Document 1's "deterministic behavior by default" principle - no random
    rounding, and never "creates" a person from a rounding-up of a
    fraction. A known, accepted simplification: the fractional remainder
    (e.g. 0.3 of a person) is dropped each month rather than carried
    forward to the next month. For small populations and small rates this
    can mean several months pass with zero effective aging - this is
    treated as expected behavior of integer-count rounding, not a bug, and
    is not addressed with a remainder-carry mechanism at this milestone
    (that would be speculative generality ahead of an actual need).
    """
    if child_count < 0:
        raise ValueError(f"child_count must be non-negative, got {child_count}")
    if rate_percent < 0:
        raise ValueError(f"rate_percent must be non-negative, got {rate_percent}")

    return math.floor(child_count * rate_percent / 100)
