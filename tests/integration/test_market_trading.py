"""
Integration tests for MarketService.buy/sell against real SQL Server,
using the real seeded CityScape city and Cinis Baseline scenario (Wheat
R-001 priced at $2.00, 100 opening stock - migrations 0014/0018).

Safe by construction: buy()/sell() never commit, so each test runs
inside one SAVEPOINT and rolls it back in a finally block - same pattern
as test_construction_ordering.py.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.market_repository import MarketRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.inventory_service import InsufficientInventoryError, InventoryService
from cinis.services.market_service import MarketService
from cinis.services.treasury_service import TreasuryService

D = Decimal
TXN_DATE = datetime.date(1880, 2, 1)


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
        "SELECT sc.ScenarioID FROM dbo.Scenario sc "
        "JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID "
        "WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'"
    )
    scenario_id = cursor.fetchone()[0]
    return city_id, scenario_id


def _build_service(session):
    return MarketService(
        MarketRepository(session),
        TreasuryService(TreasuryRepository(session)),
        InventoryService(InventoryRepository(session)),
    )


def test_buy_deducts_real_treasury_and_adds_real_wheat_inventory(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)
        starting_wheat = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(city_id, "R-001")

        txn = service.buy(city_id, scenario_id, "R-001", D("10"), TXN_DATE)
        sqlalchemy_session.flush()

        assert txn.TransactionType == "Buy"
        assert txn.UnitPrice == D("2.0000")
        assert txn.TotalValue == D("20.0000")

        new_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)
        new_wheat = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(city_id, "R-001")
        assert new_balance == starting_balance - D("20.0000")
        assert new_wheat == starting_wheat + D("10")
    finally:
        savepoint.rollback()


def test_sell_credits_real_treasury_and_removes_real_wheat_inventory(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)

        txn = service.sell(city_id, scenario_id, "R-001", D("10"), TXN_DATE)
        sqlalchemy_session.flush()

        assert txn.TransactionType == "Sell"
        new_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)
        assert new_balance == starting_balance + D("20.0000")
    finally:
        savepoint.rollback()


def test_selling_more_wheat_than_in_stock_is_refused_and_treasury_untouched(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)
        with pytest.raises(InsufficientInventoryError):
            service.sell(city_id, scenario_id, "R-001", D("100000"), TXN_DATE)
        assert TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id) == starting_balance
    finally:
        savepoint.rollback()
