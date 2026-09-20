"""Unit tests for SimulationRunRepository against a fake session (no database)."""

import datetime
from decimal import Decimal

import pytest

from cinis.models.simulation import SimulationEvent, SimulationRun
from cinis.repositories.simulation_run_repository import (
    SimulationRunNotFoundError,
    SimulationRunRepository,
    serialize_payload,
)


class FakeSession:
    def __init__(self, runs=None):
        self._runs = runs or {}
        self.added = []

    def get(self, model, key):
        assert model is SimulationRun
        return self._runs.get(key)

    def add(self, obj):
        self.added.append(obj)


def test_get_run_returns_existing_run():
    run = SimulationRun(SimulationRunID=7)
    repo = SimulationRunRepository(FakeSession({7: run}))
    assert repo.get_run(7) is run


def test_get_run_raises_clear_error_when_missing():
    repo = SimulationRunRepository(FakeSession())
    with pytest.raises(SimulationRunNotFoundError, match="SimulationRunID=99"):
        repo.get_run(99)


def test_add_event_stages_event_with_all_fields():
    session = FakeSession()
    repo = SimulationRunRepository(session)

    event = repo.add_event(
        simulation_run_id=1,
        simulation_tick_id=5,
        simulation_date=datetime.date(1880, 1, 5),
        event_type="NeedsShortfall",
        city_id=3,
        description="Food shortfall",
        payload={"ResourceCode": "R-001"},
    )

    assert session.added == [event]
    assert isinstance(event, SimulationEvent)
    assert (event.SimulationRunID, event.SimulationTickID) == (1, 5)
    assert event.SimulationDate == datetime.date(1880, 1, 5)
    assert event.CityID == 3
    assert event.EventType == "NeedsShortfall"
    assert event.Description == "Food shortfall"
    assert event.Payload == '{"ResourceCode":"R-001"}'


def test_add_event_defaults_optional_fields_to_none():
    repo = SimulationRunRepository(FakeSession())
    event = repo.add_event(1, 1, datetime.date(1880, 1, 1), "TickCompleted")
    assert event.CityID is None
    assert event.Description is None
    assert event.Payload is None


def test_serialize_payload_none_stays_none():
    assert serialize_payload(None) is None


def test_serialize_payload_is_deterministic_regardless_of_key_order():
    a = serialize_payload({"b": 1, "a": 2})
    b = serialize_payload({"a": 2, "b": 1})
    assert a == b == '{"a":2,"b":1}'


def test_serialize_payload_keeps_decimal_exact_as_string():
    text = serialize_payload({"Needed": Decimal("110.0000"), "Consumed": Decimal("100.1234")})
    assert text == '{"Consumed":"100.1234","Needed":"110.0000"}'


def test_serialize_payload_rejects_unsupported_types():
    with pytest.raises(TypeError):
        serialize_payload({"When": datetime.date(1880, 1, 1)})
