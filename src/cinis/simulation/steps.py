"""
The default M4 tick step list, in execution order.

ORDERING DECISION (flagged for the project owner, not silently assumed):
ADR-0009 Decision 1 fixes the two cadence buckets - month-boundary
(aging, then production) and every-tick (needs and consumption) - but
does not pin down the order between the two buckets within a single
month-boundary tick. This module resolves that by following Document 6's
canonical daily cycle, which lists Population/Labor, then Production,
then Inventory Ingestion, then Needs & Consumption in that order:

    1. PopulationAging   (month-boundary only)
    2. Production        (month-boundary only)
    3. NeedsConsumption  (every tick)

The consequence: on a month-boundary tick, that month's production lands
in inventory before that same day's needs consumption runs, so newly
produced FOOD/HEATING resources are available to offset consumption on
the boundary day itself. On an ordinary day, only NeedsConsumption runs.
If this ordering is wrong, it is a one-line change here - no step's own
code assumes its position in the list.
"""

from __future__ import annotations

from cinis.simulation.aging_step import make_aging_step
from cinis.simulation.needs_step import make_needs_consumption_step
from cinis.simulation.production_step import make_production_step
from cinis.simulation.tick import TickStep


def build_default_tick_steps() -> tuple[TickStep, ...]:
    """Return the M4 step list in the order SimulationEngine should run
    them. A fresh TickStep is built each call (steps are cheap, stateless
    closures), so callers get independent instances."""
    return (
        make_aging_step(),
        make_production_step(),
        make_needs_consumption_step(),
    )
