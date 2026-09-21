"""
Tick building blocks: the context a tick's steps receive, the step
definition, and the result of a completed tick.

Kept separate from the engine so steps (added in later Milestone 4 steps)
can depend on these types without importing the engine.
"""

from __future__ import annotations

import datetime
import enum
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session


class StepCadence(enum.Enum):
    """When a step runs (ADR-0009 Decision 1)."""

    # Runs on every tick (one simulated day).
    EVERY_TICK = "EveryTick"
    # Runs only on the first tick whose date falls in a new calendar month.
    MONTH_BOUNDARY = "MonthBoundary"


@dataclass(frozen=True)
class TickContext:
    """Everything a step needs to know about the tick it is running in.

    The session is the tick's single transaction: steps stage their writes
    on it and must not commit or roll back. The engine commits once after
    every step succeeds, or rolls back the whole tick if any step fails.
    """

    simulation_run_id: int
    scenario_id: int
    simulation_tick_id: int
    simulation_date: datetime.date
    previous_date: datetime.date
    is_month_boundary: bool
    session: Session


@dataclass(frozen=True)
class TickStep:
    """One named unit of work within a tick."""

    name: str
    execute: Callable[[TickContext], None]
    cadence: StepCadence = StepCadence.EVERY_TICK

    def applies_to(self, context: TickContext) -> bool:
        if self.cadence is StepCadence.MONTH_BOUNDARY:
            return context.is_month_boundary
        return True


@dataclass(frozen=True)
class TickResult:
    """The outcome of one committed tick."""

    simulation_run_id: int
    simulation_tick_id: int
    simulation_date: datetime.date
    is_month_boundary: bool
    # Names of the steps that actually ran, in execution order.
    executed_steps: tuple[str, ...]
