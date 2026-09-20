"""
Ledger trace rules: pure validation, no database access.

ADR-0009 Decision 3: a ledger entry either carries BOTH a SimulationRunID
and a SimulationTickID (written by the tick engine) or NEITHER (seed data,
tests, calls made outside a tick). SimulationTickID is a per-run counter,
so it is meaningless without its run. The database enforces the same rule
with CHECK constraints; validating here gives callers a clear error before
any write is staged.
"""

from __future__ import annotations


def validate_ledger_trace(
    simulation_run_id: int | None, simulation_tick_id: int | None
) -> None:
    """Raise ValueError unless both IDs are given or neither is, and any
    given tick is 1 or greater (ticks are numbered from 1)."""
    if (simulation_run_id is None) != (simulation_tick_id is None):
        raise ValueError(
            "simulation_run_id and simulation_tick_id must be given together "
            f"or not at all, got run={simulation_run_id!r}, tick={simulation_tick_id!r}"
        )
    if simulation_tick_id is not None and simulation_tick_id < 1:
        raise ValueError(f"simulation_tick_id must be 1 or greater, got {simulation_tick_id}")
