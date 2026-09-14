"""
Integration tests for Treasury, run against real SQL Server with
CityScape's actual seeded 10,000 STD opening balance.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pyodbc
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.treasury_repository import (
    TreasuryCategoryTypeNotFoundError,
    TreasuryRepository,
)
from cinis.services.treasury_service import TreasuryService


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


def test_cityscape_has_seeded_treasury_with_opening_balance(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT t.Balance FROM dbo.Treasury t
        JOIN dbo.City c ON c.CityID = t.CityID
        WHERE c.Name = 'CityScape'
        """
    )
    row = cursor.fetchone()
    assert row is not None
    assert Decimal(str(row[0])) == Decimal("10000.0000")


def test_opening_balance_ledger_entry_exists(connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT tle.Amount, tct.Code
        FROM dbo.TreasuryLedgerEntry tle
        JOIN dbo.Treasury t ON t.TreasuryID = tle.TreasuryID
        JOIN dbo.City c ON c.CityID = t.CityID
        JOIN dbo.TreasuryCategoryType tct ON tct.TreasuryCategoryTypeID = tle.TreasuryCategoryTypeID
        WHERE c.Name = 'CityScape' AND tct.Code = 'OPENING_BALANCE'
        """
    )
    row = cursor.fetchone()
    assert row is not None
    assert Decimal(str(row[0])) == Decimal("10000.0000")


def test_treasury_is_unique_per_city(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]

    with pytest.raises(pyodbc.Error):
        cursor.execute(
            "INSERT INTO dbo.Treasury (CityID, CurrencyID, Balance) "
            "SELECT ?, CurrencyID, 0 FROM dbo.Currency WHERE Code = 'STD'",
            city_id,
        )
        connection.commit()
    connection.rollback()


def test_record_ledger_entry_updates_balance_and_persists(
    sqlalchemy_session, cityscape_id
):
    repo = TreasuryRepository(sqlalchemy_session)
    service = TreasuryService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = service.get_balance(cityscape_id)
        assert starting_balance == Decimal("10000.0000")

        result = service.record_ledger_entry(
            city_id=cityscape_id,
            category_code="RESIDENT_INCOME",
            amount=Decimal("1252.06"),
            entry_date=date(2026, 2, 1),
        )
        sqlalchemy_session.flush()

        assert result.new_balance == Decimal("11252.0600")

        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            "SELECT Balance FROM dbo.Treasury WHERE CityID = ?", cityscape_id
        )
        assert Decimal(str(cursor.fetchone()[0])) == Decimal("11252.0600")
    finally:
        savepoint.rollback()

    # Confirm rollback actually restored the real seeded balance.
    restored_balance = service.get_balance(cityscape_id)
    assert restored_balance == Decimal("10000.0000")


def test_record_expense_entry_decreases_balance(sqlalchemy_session, cityscape_id):
    repo = TreasuryRepository(sqlalchemy_session)
    service = TreasuryService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        result = service.record_ledger_entry(
            city_id=cityscape_id,
            category_code="BUILDING_MAINTENANCE",
            amount=Decimal("-20.00"),
            entry_date=date(2026, 2, 1),
        )
        assert result.new_balance == Decimal("9980.0000")
    finally:
        savepoint.rollback()


def test_unknown_category_code_raises_clear_error(sqlalchemy_session, cityscape_id):
    repo = TreasuryRepository(sqlalchemy_session)
    service = TreasuryService(repo)

    with pytest.raises(TreasuryCategoryTypeNotFoundError):
        service.record_ledger_entry(
            city_id=cityscape_id,
            category_code="NOT_A_REAL_CATEGORY",
            amount=Decimal("100.00"),
            entry_date=date(2026, 2, 1),
        )
