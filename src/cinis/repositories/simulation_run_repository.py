"""
Simulation run repository. Isolates all SQL access for SimulationRun reads
and the SimulationEvent log, per Document 6's layering.

Scope (Milestone 4, Step 4.1): read a run, append events, read a tick's
events. It deliberately does NOT advance a run's date/tick or change its
status - that is state mutation and belongs in the service layer (Step
4.3), built on the calendar rules from Step 4.2. Callers own the
transaction boundary; nothing here commits.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from cinis.models.simulation import SimulationEvent, SimulationRun


class SimulationRunNotFoundError(RuntimeError):
    """Raised when a requested SimulationRun does not exist."""


def _json_default(value: Any) -> str:
    # Decimal is the project's quantity type and is not natively JSON
    # serializable. Store it as its exact string form rather than a float,
    # so no precision is lost (determinism principle).
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Event payload value of type {type(value).__name__} is not serializable")


def serialize_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Serialize an event payload to deterministic JSON text (sorted keys,
    no incidental whitespace). None stays None."""
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


class SimulationRunRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_run(self, simulation_run_id: int) -> SimulationRun:
        run = self._session.get(SimulationRun, simulation_run_id)
        if run is None:
            raise SimulationRunNotFoundError(
                f"SimulationRunID={simulation_run_id} does not exist."
            )
        return run

    def add_event(
        self,
        simulation_run_id: int,
        simulation_tick_id: int,
        simulation_date: datetime.date,
        event_type: str,
        city_id: int | None = None,
        description: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> SimulationEvent:
        """Create and stage a new event. Does not commit; the caller (the
        tick engine) owns the transaction boundary."""
        event = SimulationEvent(
            SimulationRunID=simulation_run_id,
            SimulationTickID=simulation_tick_id,
            SimulationDate=simulation_date,
            CityID=city_id,
            EventType=event_type,
            Description=description,
            Payload=serialize_payload(payload),
        )
        self._session.add(event)
        return event

    def get_events_for_tick(
        self, simulation_run_id: int, simulation_tick_id: int
    ) -> list[SimulationEvent]:
        """Return a tick's events in insertion order (by SimulationEventID),
        so results are deterministic."""
        self._session.flush()
        return (
            self._session.query(SimulationEvent)
            .filter(
                SimulationEvent.SimulationRunID == simulation_run_id,
                SimulationEvent.SimulationTickID == simulation_tick_id,
            )
            .order_by(SimulationEvent.SimulationEventID)
            .all()
        )
