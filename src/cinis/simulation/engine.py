"""
SimulationEngine: runs one tick at a time as a single database transaction.

Per Document 6 the engine orchestrates; it contains no business logic. The
work of a tick lives in an ordered list of TickSteps supplied by the caller
(the real steps are added in later Milestone 4 steps).

One tick = one transaction (Document 7: "no partial persistence after
failed ticks"):
  1. Load the run and check it is Active.
  2. Advance the run's date and tick (rules/calendar_rules.py).
  3. Run each applicable step, in order, on the tick's session.
  4. Commit once.
If anything in steps 2-4 raises, the whole tick is rolled back, the run is
then marked Failed in a separate short transaction, and the ORIGINAL
exception is re-raised. A failed run is not ticked again.

Steps must not commit or roll back. Time progresses only through the run's
SimulationDate and SimulationTickID; nothing here reads the wall clock.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from cinis.models.simulation import SimulationRun
from cinis.repositories.simulation_run_repository import SimulationRunRepository
from cinis.rules.calendar_rules import advance_tick
from cinis.simulation.tick import TickContext, TickResult, TickStep

logger = logging.getLogger(__name__)

ACTIVE_STATUS = "Active"
FAILED_STATUS = "Failed"


class SimulationRunNotActiveError(RuntimeError):
    """Raised when a tick is requested for a run whose Status is not
    Active. This is a precondition failure, not a tick failure: nothing is
    rolled back and the run's status is left as it was."""


class SimulationEngine:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        steps: Sequence[TickStep] = (),
    ):
        names = [step.name for step in steps]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Tick step names must be unique, duplicated: {duplicates}")

        self._session_factory = session_factory
        self._steps = tuple(steps)

    def run_tick(self, simulation_run_id: int) -> TickResult:
        """Advance a run by one tick and commit it, or roll it back entirely.

        Raises SimulationRunNotFoundError or SimulationRunNotActiveError
        (before anything changes) if the run cannot be ticked. If a step or
        the commit fails, the tick is rolled back, the run is marked Failed,
        and the original exception propagates.
        """
        session = self._session_factory()
        try:
            run = SimulationRunRepository(session).get_run(simulation_run_id)
            if run.Status != ACTIVE_STATUS:
                raise SimulationRunNotActiveError(
                    f"SimulationRunID={simulation_run_id} has Status={run.Status!r}; "
                    f"only {ACTIVE_STATUS!r} runs can be ticked."
                )

            try:
                result = self._execute_tick(session, run)
                session.commit()
            except Exception:
                session.rollback()
                self._mark_run_failed(simulation_run_id)
                raise

            logger.info(
                "Run %s tick %s (%s) committed; steps: %s",
                result.simulation_run_id,
                result.simulation_tick_id,
                result.simulation_date,
                ", ".join(result.executed_steps) or "none",
            )
            return result
        finally:
            session.close()

    def _execute_tick(self, session: Session, run: SimulationRun) -> TickResult:
        advance = advance_tick(run.CurrentSimulationDate, run.CurrentSimulationTickID)

        run.CurrentSimulationDate = advance.new_date
        run.CurrentSimulationTickID = advance.new_tick_id

        context = TickContext(
            simulation_run_id=run.SimulationRunID,
            scenario_id=run.ScenarioID,
            simulation_tick_id=advance.new_tick_id,
            simulation_date=advance.new_date,
            previous_date=advance.previous_date,
            is_month_boundary=advance.is_month_boundary,
            session=session,
        )

        executed: list[str] = []
        for step in self._steps:
            if not step.applies_to(context):
                continue
            try:
                step.execute(context)
            except Exception:
                logger.error(
                    "Run %s tick %s failed in step %r; rolling back the tick.",
                    context.simulation_run_id,
                    context.simulation_tick_id,
                    step.name,
                    exc_info=True,
                )
                raise
            executed.append(step.name)

        return TickResult(
            simulation_run_id=context.simulation_run_id,
            simulation_tick_id=context.simulation_tick_id,
            simulation_date=context.simulation_date,
            is_month_boundary=context.is_month_boundary,
            executed_steps=tuple(executed),
        )

    def _mark_run_failed(self, simulation_run_id: int) -> None:
        """Record Status=Failed in its own transaction, after the tick's
        rollback. Best effort: if this also fails, log it and let the
        caller re-raise the original error."""
        try:
            session = self._session_factory()
            try:
                run = SimulationRunRepository(session).get_run(simulation_run_id)
                run.Status = FAILED_STATUS
                session.commit()
            finally:
                session.close()
        except Exception:
            logger.error(
                "Could not record Status=%r for run %s after a failed tick.",
                FAILED_STATUS,
                simulation_run_id,
                exc_info=True,
            )
