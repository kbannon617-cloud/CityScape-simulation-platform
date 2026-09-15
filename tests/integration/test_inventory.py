"""
Integration tests for CityInventory/InventoryLedgerEntry, run against
real SQL Server with the actual seeded CityScape data (100 Wheat, 100
Timber).
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.services.inventory_service import InsufficientInventoryError, InventoryService


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


def test_wheat_and_timber_seeded_at_100(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT r.Code, ci.Quantity FROM dbo.CityInventory ci
        JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID
        JOIN dbo.City c ON c.CityID = ci.CityID
        WHERE c.Name = 'CityScape'
        """
    )
    rows = {code: qty for code, qty in cursor.fetchall()}
    assert Decimal(str(rows["R-001"])) == Decimal("100.0000")
    assert Decimal(str(rows["R-004"])) == Decimal("100.0000")


def test_other_resources_have_no_inventory_row_meaning_zero_stock(connection, cityscape_id):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM dbo.CityInventory WHERE CityID = ?", cityscape_id
    )
    assert cursor.fetchone()[0] == 2  # only Wheat and Timber


def test_repository_get_quantity_returns_zero_for_unseeded_resource(
    sqlalchemy_session, cityscape_id
):
    repo = InventoryRepository(sqlalchemy_session)
    assert repo.get_quantity(cityscape_id, "R-002") == Decimal("0")  # Trout, never seeded


def test_service_records_production_output_within_a_savepoint(sqlalchemy_session, cityscape_id):
    repo = InventoryRepository(sqlalchemy_session)
    service = InventoryService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute("SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
        wheat_id = cursor.fetchone()[0]

        result = service.record_ledger_entry(
            city_id=cityscape_id,
            resource_id=wheat_id,
            amount=Decimal("100"),
            entry_date=datetime.date(2026, 2, 1),
            notes="Simulated production output.",
        )
        sqlalchemy_session.flush()

        assert result.new_quantity == Decimal("200")
        assert repo.get_quantity(cityscape_id, "R-001") == Decimal("200")
    finally:
        savepoint.rollback()

    # Confirm rollback actually restored the real seeded value.
    assert repo.get_quantity(cityscape_id, "R-001") == Decimal("100")


def test_service_rejects_consumption_that_would_go_negative(sqlalchemy_session, cityscape_id):
    repo = InventoryRepository(sqlalchemy_session)
    service = InventoryService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute("SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001'")
        wheat_id = cursor.fetchone()[0]

        with pytest.raises(InsufficientInventoryError):
            service.record_ledger_entry(
                city_id=cityscape_id,
                resource_id=wheat_id,
                amount=Decimal("-1000"),
                entry_date=datetime.date(2026, 2, 1),
            )
    finally:
        savepoint.rollback()

    assert repo.get_quantity(cityscape_id, "R-001") == Decimal("100")


def test_database_check_constraint_also_rejects_direct_negative_write(connection, cityscape_id):
    """Confirms the DB-level safety net independently of the service
    layer's own pre-check - a direct raw INSERT/UPDATE bypassing
    InventoryService should still be rejected."""
    import pyodbc

    cursor = connection.cursor()
    with pytest.raises(pyodbc.Error):
        cursor.execute(
            """
            UPDATE dbo.CityInventory SET Quantity = -5
            WHERE CityID = ? AND ResourceID = (SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-001')
            """,
            cityscape_id,
        )
        connection.commit()
    connection.rollback()
