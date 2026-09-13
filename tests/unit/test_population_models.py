"""Unit tests verifying the population ORM models map to the physical schema."""

from cinis.models.population import PopulationGroup, PopulationGroupType, ScenarioParameter


def test_population_group_type_maps_to_expected_table():
    assert PopulationGroupType.__tablename__ == "PopulationGroupType"
    columns = {c.name for c in PopulationGroupType.__table__.columns}
    assert columns == {"PopulationGroupTypeID", "Code", "Name", "CreatedDateTime"}


def test_population_group_has_foreign_keys_to_city_and_group_type():
    fk_targets = {fk.target_fullname for fk in PopulationGroup.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert "PopulationGroupType.PopulationGroupTypeID" in fk_targets


def test_scenario_parameter_has_foreign_key_to_scenario():
    fk_targets = {fk.target_fullname for fk in ScenarioParameter.__table__.foreign_keys}
    assert "Scenario.ScenarioID" in fk_targets


def test_scenario_parameter_value_is_numeric_not_float():
    from sqlalchemy import Numeric

    column = ScenarioParameter.__table__.columns["ParameterValue"]
    assert isinstance(column.type, Numeric)
