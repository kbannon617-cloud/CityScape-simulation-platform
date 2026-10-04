"""Unit tests for the two new repository write methods (Step 4.6a/b),
against minimal fakes - no database."""

import datetime
from decimal import Decimal

from cinis.models.market import MarketTransaction
from cinis.models.vehicle import CityVehicle
from cinis.repositories.market_repository import MarketRepository
from cinis.repositories.vehicle_repository import VehicleRepository

D = Decimal


class _FakeSession:
    def __init__(self, existing=None):
        self.added = []
        self._existing = existing

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def query(self, model):
        return self

    def filter(self, *a, **k):
        return self

    def one_or_none(self):
        return self._existing


def test_record_transaction_stages_without_committing():
    session = _FakeSession()
    repo = MarketRepository(session)

    txn = repo.record_transaction(
        market_id=9, resource_id=1, transaction_type="Buy",
        quantity=D("10"), unit_price=D("2.00"), total_value=D("20.00"),
        transaction_date=datetime.date(1880, 2, 1),
    )

    assert session.added == [txn]
    assert isinstance(txn, MarketTransaction)
    assert txn.TransactionType == "Buy"
    assert txn.TotalValue == D("20.00")


def test_get_or_create_city_vehicle_creates_at_zero_when_missing():
    session = _FakeSession(existing=None)
    repo = VehicleRepository(session)

    vehicle = repo.get_or_create_city_vehicle(city_id=1, vehicle_type_id=2)

    assert session.added == [vehicle]
    assert isinstance(vehicle, CityVehicle)
    assert vehicle.Count == 0


def test_get_or_create_city_vehicle_returns_existing_without_creating():
    existing = CityVehicle(CityID=1, VehicleTypeID=2, Count=5)
    session = _FakeSession(existing=existing)
    repo = VehicleRepository(session)

    vehicle = repo.get_or_create_city_vehicle(city_id=1, vehicle_type_id=2)

    assert vehicle is existing
    assert session.added == []
