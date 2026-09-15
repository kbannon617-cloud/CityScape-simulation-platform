"""Unit tests verifying the production/inventory ORM models map to the physical schema."""

from cinis.models.inventory import Resource
from cinis.models.production import Building, BuildingType, ProductionFlow


def test_resource_maps_to_expected_table():
    assert Resource.__tablename__ == "Resource"
    fk_targets = {fk.target_fullname for fk in Resource.__table__.foreign_keys}
    assert "UnitOfMeasure.UnitOfMeasureID" in fk_targets


def test_building_type_maps_to_expected_table():
    assert BuildingType.__tablename__ == "BuildingType"


def test_building_type_has_no_output_columns():
    columns = {c.name for c in BuildingType.__table__.columns}
    assert "MonthlyOutput" not in columns
    assert "OutputResource" not in columns


def test_building_has_foreign_keys_to_city_and_building_type():
    fk_targets = {fk.target_fullname for fk in Building.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert "BuildingType.BuildingTypeID" in fk_targets


def test_production_flow_has_foreign_keys_to_building_type_and_resource():
    fk_targets = {fk.target_fullname for fk in ProductionFlow.__table__.foreign_keys}
    assert "BuildingType.BuildingTypeID" in fk_targets
    assert "Resource.ResourceID" in fk_targets
