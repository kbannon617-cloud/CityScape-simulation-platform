"""
Unit tests verifying the ORM models map to the correct table and column
names, without needing a live database. This catches typos or mismatches
against the physical schema (database/migrations/0002_*.sql) at import
time, before anyone tries to actually query with them.
"""

from cinis.models.geography import City, Region, World
from cinis.models.reference import Currency, UnitOfMeasure
from cinis.models.simulation import Scenario, Simulation, SimulationRun


def test_currency_maps_to_expected_table_and_columns():
    assert Currency.__tablename__ == "Currency"
    columns = {c.name for c in Currency.__table__.columns}
    assert columns == {"CurrencyID", "Code", "Name", "Symbol", "CreatedDateTime"}


def test_unit_of_measure_maps_to_expected_table_and_columns():
    assert UnitOfMeasure.__tablename__ == "UnitOfMeasure"
    columns = {c.name for c in UnitOfMeasure.__table__.columns}
    assert columns == {"UnitOfMeasureID", "Code", "Name", "CreatedDateTime"}


def test_world_region_city_map_to_expected_tables():
    assert World.__tablename__ == "World"
    assert Region.__tablename__ == "Region"
    assert City.__tablename__ == "City"


def test_city_has_is_primary_active_column():
    columns = {c.name for c in City.__table__.columns}
    assert "IsPrimaryActive" in columns


def test_region_has_foreign_key_to_world():
    fk_targets = {fk.target_fullname for fk in Region.__table__.foreign_keys}
    assert "World.WorldID" in fk_targets


def test_city_has_foreign_key_to_region():
    fk_targets = {fk.target_fullname for fk in City.__table__.foreign_keys}
    assert "Region.RegionID" in fk_targets


def test_simulation_scenario_simulationrun_map_to_expected_tables():
    assert Simulation.__tablename__ == "Simulation"
    assert Scenario.__tablename__ == "Scenario"
    assert SimulationRun.__tablename__ == "SimulationRun"


def test_scenario_has_self_referencing_parent_foreign_key():
    fk_targets = {fk.target_fullname for fk in Scenario.__table__.foreign_keys}
    assert "Scenario.ScenarioID" in fk_targets


def test_simulation_run_current_tick_id_is_bigint():
    from sqlalchemy import BigInteger

    column = SimulationRun.__table__.columns["CurrentSimulationTickID"]
    assert isinstance(column.type, BigInteger)
