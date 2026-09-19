"""
Integration tests for Market/MarketResourcePrice, run against real
SQL Server with the actual seeded CityScape data.
"""

from __future__ import annotations

from decimal import Decimal

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.market_repository import MarketRepository, ResourcePriceNotFoundError


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cityscape_and_baseline_ids(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT sc.ScenarioID FROM dbo.Scenario sc
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
        """
    )
    scenario_id = cursor.fetchone()[0]
    return city_id, scenario_id


def test_cityscape_has_exactly_one_market(connection, cityscape_and_baseline_ids):
    city_id, _ = cityscape_and_baseline_ids
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.Market WHERE CityID = ?", city_id)
    assert cursor.fetchone()[0] == 1


def test_all_eleven_resources_have_a_seeded_price(connection, cityscape_and_baseline_ids):
    _, scenario_id = cityscape_and_baseline_ids
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM dbo.MarketResourcePrice WHERE ScenarioID = ?", scenario_id
    )
    assert cursor.fetchone()[0] == 11


def test_wheat_price_matches_seeded_value(connection, cityscape_and_baseline_ids):
    _, scenario_id = cityscape_and_baseline_ids
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT mrp.UnitPrice FROM dbo.MarketResourcePrice mrp
        JOIN dbo.Resource r ON r.ResourceID = mrp.ResourceID
        WHERE mrp.ScenarioID = ? AND r.Code = 'R-001'
        """,
        scenario_id,
    )
    assert Decimal(str(cursor.fetchone()[0])) == Decimal("2.0000")


def test_market_transaction_rejects_zero_quantity(connection, cityscape_and_baseline_ids):
    city_id, _ = cityscape_and_baseline_ids
    cursor = connection.cursor()
    cursor.execute("SELECT MarketID FROM dbo.Market WHERE CityID = ?", city_id)
    market_id = cursor.fetchone()[0]
    cursor.execute("SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
    resource_id = cursor.fetchone()[0]

    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.MarketTransaction "
            "(MarketID, ResourceID, TransactionType, Quantity, UnitPrice, TotalValue, TransactionDate) "
            "VALUES (?, ?, 'Sell', 0, 2.00, 0, '2026-02-01')",
            market_id,
            resource_id,
        )
        connection.commit()
    connection.rollback()


def test_repository_get_market_and_price(sqlalchemy_session, cityscape_and_baseline_ids):
    city_id, scenario_id = cityscape_and_baseline_ids
    repo = MarketRepository(sqlalchemy_session)

    market = repo.get_market(city_id)
    assert market.CityID == city_id

    price = repo.get_resource_price(scenario_id, "R-004")  # Timber
    assert price == Decimal("1.5000")


def test_repository_raises_for_unpriced_resource(sqlalchemy_session, cityscape_and_baseline_ids):
    _, scenario_id = cityscape_and_baseline_ids
    repo = MarketRepository(sqlalchemy_session)

    with pytest.raises(ResourcePriceNotFoundError):
        repo.get_resource_price(scenario_id, "R-999")
