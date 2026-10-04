"""
Integration tests for VehicleOrderingService.order_vehicles against real
SQL Server, using the real seeded CityScape city (V-001 Boat: Timber 50,
Stone 0 - migration 0015/0016).

Safe by construction: order_vehicles() never commits, so each test runs
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
from cinis.repositories.vehicle_repository import VehicleRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.vehicle_ordering_service import VehicleOrderingService

ORDER_DATE = datetime.date(1880, 2, 1)


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


def _build_service(session):
    return VehicleOrderingService(VehicleRepository(session), InventoryService(InventoryRepository(session)))


def test_orders_a_boat_and_deducts_real_timber_only(sqlalchemy_session, cityscape_id):
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_timber = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(
            cityscape_id, "R-004"
        )

        vehicle = service.order_vehicles(cityscape_id, "V-001", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        assert vehicle.Count == 1
        new_timber = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(
            cityscape_id, "R-004"
        )
        assert new_timber == starting_timber - 50
    finally:
        savepoint.rollback()


def test_a_second_order_adds_to_the_existing_count(sqlalchemy_session, cityscape_id):
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        # Real Timber stock is only 100 (migration 0014); this test's two
        # orders need 150 total (50 + 100), so top it up first - same
        # lesson as the Stone top-up in test_construction_ordering.py.
        InventoryService(InventoryRepository(sqlalchemy_session)).record_ledger_entry(
            city_id=cityscape_id,
            resource_id=InventoryService(InventoryRepository(sqlalchemy_session)).get_resource_id("R-004"),
            amount=Decimal("1000"),
            entry_date=ORDER_DATE,
            notes="Test-seeded stock.",
        )
        sqlalchemy_session.flush()

        service.order_vehicles(cityscape_id, "V-001", 1, ORDER_DATE)
        sqlalchemy_session.flush()
        vehicle = service.order_vehicles(cityscape_id, "V-001", 2, ORDER_DATE)
        sqlalchemy_session.flush()

        assert vehicle.Count == 3
    finally:
        savepoint.rollback()


def test_insufficient_timber_is_refused(sqlalchemy_session, cityscape_id):
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        from cinis.services.inventory_service import InsufficientInventoryError

        with pytest.raises(InsufficientInventoryError):
            service.order_vehicles(cityscape_id, "V-001", 1000, ORDER_DATE)
    finally:
        savepoint.rollback()
