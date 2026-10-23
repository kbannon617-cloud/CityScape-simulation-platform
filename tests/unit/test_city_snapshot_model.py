"""Unit tests verifying the CitySnapshot model maps to migration 0026."""

from sqlalchemy import BigInteger, UnicodeText

from cinis.models.simulation import CitySnapshot


def test_uses_bigint_primary_key():
    column = CitySnapshot.__table__.columns["CitySnapshotID"]
    assert isinstance(column.type, BigInteger)
    assert column.primary_key


def test_has_foreign_keys_to_run_and_city():
    fk_targets = {fk.target_fullname for fk in CitySnapshot.__table__.foreign_keys}
    assert fk_targets == {"SimulationRun.SimulationRunID", "City.CityID"}


def test_city_id_and_payload_are_not_nullable_unlike_simulation_event():
    columns = CitySnapshot.__table__.columns
    assert not columns["CityID"].nullable
    assert not columns["Payload"].nullable
    assert isinstance(columns["Payload"].type, UnicodeText)


def test_check_constraints_match_migration():
    names = {c.name for c in CitySnapshot.__table__.constraints if c.name}
    assert names == {
        "CK_CitySnapshot_SimulationTickID_Positive",
        "CK_CitySnapshot_Payload_IsJson",
    }


def test_is_registered_in_models_package():
    import cinis.models as models

    assert models.CitySnapshot is CitySnapshot
    assert "CitySnapshot" in models.__all__


def test_relationships_resolve_against_the_full_mapper_configuration():
    from sqlalchemy.orm import configure_mappers

    import cinis.models  # noqa: F401

    configure_mappers()
