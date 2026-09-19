"""
Integration tests for the vehicle catalog, run against real SQL Server
with the actual seeded data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.vehicle_repository import VehicleRepository, VehicleTypeNotFoundError


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cityscape_id(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    return cursor.fetchone()[0]


def test_two_vehicle_types_seeded(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.VehicleType")
    assert cursor.fetchone()[0] == 2


def test_one_transport_mode_seeded_and_linked_to_cart(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT tm.Code, vt.Code FROM dbo.TransportMode tm
        JOIN dbo.VehicleType vt ON vt.VehicleTypeID = tm.VehicleTypeID
        """
    )
    row = cursor.fetchone()
    assert tuple(row) == ("TM-001", "V-002")


def test_trout_fishery_requires_boat_with_one_included(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT bvr.CapacityPerBuilding, bvr.IncludedPerBuilding
        FROM dbo.BuildingVehicleRequirement bvr
        JOIN dbo.BuildingType bt ON bt.BuildingTypeID = bvr.BuildingTypeID
        JOIN dbo.VehicleType vt ON vt.VehicleTypeID = bvr.VehicleTypeID
        WHERE bt.Name = 'Trout Fishery' AND vt.Code = 'V-001'
        """
    )
    capacity, included = cursor.fetchone()
    assert capacity == 2
    assert included == 1


def test_cityscape_owns_zero_vehicles(connection, cityscape_id):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.CityVehicle WHERE CityID = ?", cityscape_id)
    assert cursor.fetchone()[0] == 0


def test_repository_get_city_vehicles_returns_empty_dict(sqlalchemy_session, cityscape_id):
    repo = VehicleRepository(sqlalchemy_session)
    assert repo.get_city_vehicles(cityscape_id) == {}


def test_repository_get_vehicle_requirement_for_wheat_farm_is_none(sqlalchemy_session):
    """Wheat Farm doesn't require any vehicle - confirms the lookup
    correctly returns None rather than erroring for the common case."""
    repo = VehicleRepository(sqlalchemy_session)
    assert repo.get_vehicle_requirement_for_building_type("B-002") is None


def test_repository_raises_for_unknown_vehicle_type(sqlalchemy_session):
    repo = VehicleRepository(sqlalchemy_session)
    with pytest.raises(VehicleTypeNotFoundError):
        repo.get_vehicle_type("V-999")
