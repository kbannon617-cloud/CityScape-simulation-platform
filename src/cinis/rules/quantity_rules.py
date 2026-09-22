"""
Quantity rules: pure Decimal helpers, no database access.

Ledger quantities are DECIMAL(18,4). Per Document 1's determinism principle,
any reduction to that precision uses floor - never round-half-up and never
anything random - so the same inputs always give the same ledger amounts.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

LEDGER_PRECISION = Decimal("0.0001")


def floor_to_ledger_precision(value: Decimal) -> Decimal:
    """Reduce value to four decimal places by rounding toward negative
    infinity."""
    return value.quantize(LEDGER_PRECISION, rounding=ROUND_FLOOR)
