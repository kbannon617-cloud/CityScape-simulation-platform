"""Unit tests verifying the SimulationEvent model maps to migration 0019."""

from sqlalchemy import BigInteger, Date

from cinis.models.simulation import SimulationEvent


def test_uses_bigint_primary_key():
    column = SimulationEvent.__table__.columns["SimulationEventID"]
    assert isinstance(column.type, BigInteger)
    assert column.primary_key


def test_tick_is_bigint_and_date_is_date():
    columns = SimulationEvent.__table__.columns
    assert isinstance(columns["SimulationTickID"].type, BigInteger)
    assert isinstance(columns["SimulationDate"].type, Date)


def test_has_foreign_keys_to_run_and_city():
    fk_targets = {fk.target_fullname for fk in SimulationEvent.__table__.foreign_keys}
    assert fk_targets == {"SimulationRun.SimulationRunID", "City.CityID"}


def test_city_description_and_payload_are_nullable():
    columns = SimulationEvent.__table__.columns
    assert columns["CityID"].nullable
    assert columns["Description"].nullable
    assert columns["Payload"].nullable


def test_required_columns_are_not_nullable():
    columns = SimulationEvent.__table__.columns
    for name in ("SimulationRunID", "SimulationTickID", "SimulationDate", "EventType"):
        assert not columns[name].nullable


def test_check_constraints_match_migration():
    names = {c.name for c in SimulationEvent.__table__.constraints if c.name}
    assert "CK_SimulationEvent_SimulationTickID_Positive" in names
    assert "CK_SimulationEvent_Payload_IsJson" in names


def test_is_registered_in_models_package():
    import cinis.models as models

    assert models.SimulationEvent is SimulationEvent
    assert "SimulationEvent" in models.__all__
