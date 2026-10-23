"""
Snapshot repository. Isolates all SQL access for CitySnapshot - the
SNAPSHOTS leg of CURRENT STATE + EVENTS + SNAPSHOTS (migration 0026).
Mirrors SimulationRunRepository.add_event's shape exactly.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from cinis.models.simulation import CitySnapshot
from cinis.repositories.simulation_run_repository import serialize_payload


class SnapshotRepository:
    def __init__(self, session: Session):
        self._session = session

    def record_snapshot(
        self,
        simulation_run_id: int,
        simulation_tick_id: int,
        simulation_date: datetime.date,
        city_id: int,
        payload: Mapping[str, Any],
    ) -> CitySnapshot:
        """Create and stage a new snapshot. Does not commit; the caller
        (the tick engine) owns the transaction boundary. payload is
        required (unlike SimulationEvent.Payload) - a snapshot with no
        state in it is meaningless."""
        snapshot = CitySnapshot(
            SimulationRunID=simulation_run_id,
            SimulationTickID=simulation_tick_id,
            SimulationDate=simulation_date,
            CityID=city_id,
            Payload=serialize_payload(payload),
        )
        self._session.add(snapshot)
        return snapshot
