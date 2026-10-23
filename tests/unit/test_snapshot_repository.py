"""Unit tests for SnapshotRepository.record_snapshot against a fake session (no database)."""

import datetime

from cinis.models.simulation import CitySnapshot
from cinis.repositories.snapshot_repository import SnapshotRepository


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_record_snapshot_stages_a_serialized_payload_without_committing():
    session = _FakeSession()
    repo = SnapshotRepository(session)

    snapshot = repo.record_snapshot(
        simulation_run_id=1,
        simulation_tick_id=30,
        simulation_date=datetime.date(1880, 2, 1),
        city_id=2,
        payload={"b": 1, "a": 2},
    )

    assert session.added == [snapshot]
    assert isinstance(snapshot, CitySnapshot)
    assert (snapshot.SimulationRunID, snapshot.SimulationTickID) == (1, 30)
    assert snapshot.CityID == 2
    assert snapshot.SimulationDate == datetime.date(1880, 2, 1)
    assert snapshot.Payload == '{"a":2,"b":1}'
