"""
Integration tests for the production catalog (Resource, BuildingType,
Building, ProductionFlow), run against real SQL Server with the actual
seeded CityScape data.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.production_repository import (
    BuildingTypeNotFoundError,
    ProductionRepository,
)


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


def test_all_eleven_resources_seeded_with_ea_unit(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT r.Code, u.Code FROM dbo.Resource r
        JOIN dbo.UnitOfMeasure u ON u.UnitOfMeasureID = r.UnitOfMeasureID
        """
    )
    rows = {code: unit for code, unit in cursor.fetchall()}
    assert len(rows) == 11
    assert all(unit == "EA" for unit in rows.values())


def test_flax_eggs_ore_have_corrected_resource_ids(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT Code, Name FROM dbo.Resource WHERE Code IN ('R-008', 'R-009', 'R-011')")
    rows = {code: name for code, name in cursor.fetchall()}
    assert rows == {"R-008": "Flax", "R-009": "Eggs", "R-011": "Ore"}


def test_fifteen_building_types_seeded(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.BuildingType")
    assert cursor.fetchone()[0] == 15


def test_cityscape_starts_with_cottages_and_wheat_farm(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT bt.Code, b.Count FROM dbo.Building b
        JOIN dbo.City c ON c.CityID = b.CityID
        JOIN dbo.BuildingType bt ON bt.BuildingTypeID = b.BuildingTypeID
        WHERE c.Name = 'CityScape'
        """
    )
    rows = {code: count for code, count in cursor.fetchall()}
    assert rows == {"B-001": 3, "B-002": 1}


def test_eleven_production_flows_seeded(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.ProductionFlow")
    assert cursor.fetchone()[0] == 11


def test_saw_mill_input_flow_references_correct_timber_resource(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT r.Name, pf.FlowType, pf.UnitsPerBuildingPerMonth
        FROM dbo.ProductionFlow pf
        JOIN dbo.BuildingType bt ON bt.BuildingTypeID = pf.BuildingTypeID
        JOIN dbo.Resource r ON r.ResourceID = pf.ResourceID
        WHERE bt.Code = 'B-009' AND pf.FlowType = 'Input'
        """
    )
    row = cursor.fetchone()
    assert row[0] == "Timber"
    assert Decimal(str(row[2])) == Decimal("100.0000")


def test_production_repository_get_city_buildings(sqlalchemy_session, cityscape_id):
    repo = ProductionRepository(sqlalchemy_session)

    buildings = repo.get_city_buildings(cityscape_id)

    assert buildings == {"B-001": 3, "B-002": 1}


def test_production_repository_get_flows_for_wheat_farm(sqlalchemy_session):
    repo = ProductionRepository(sqlalchemy_session)

    flows = repo.get_flows_for_building_type("B-002")

    assert len(flows) == 1
    assert flows[0].FlowType == "Output"
    assert flows[0].resource.Name == "Wheat"


def test_production_repository_raises_for_unknown_building_type(sqlalchemy_session):
    repo = ProductionRepository(sqlalchemy_session)

    with pytest.raises(BuildingTypeNotFoundError):
        repo.get_building_type("B-999")
