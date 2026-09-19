"""Unit tests verifying the vehicle ORM models map to the physical schema."""

from cinis.models.vehicle import BuildingVehicleRequirement, CityVehicle, TransportMode, VehicleType


def test_vehicle_type_maps_to_expected_table():
    assert VehicleType.__tablename__ == "VehicleType"


def test_transport_mode_has_foreign_key_to_vehicle_type():
    fk_targets = {fk.target_fullname for fk in TransportMode.__table__.foreign_keys}
    assert "VehicleType.VehicleTypeID" in fk_targets


def test_building_vehicle_requirement_has_expected_foreign_keys():
    fk_targets = {fk.target_fullname for fk in BuildingVehicleRequirement.__table__.foreign_keys}
    assert "BuildingType.BuildingTypeID" in fk_targets
    assert "VehicleType.VehicleTypeID" in fk_targets


def test_city_vehicle_has_foreign_keys_to_city_and_vehicle_type():
    fk_targets = {fk.target_fullname for fk in CityVehicle.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert "VehicleType.VehicleTypeID" in fk_targets
