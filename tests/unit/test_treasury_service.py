"""
Unit tests for TreasuryService, using a fake repository rather than a real
database. Real SQL behavior is covered in tests/integration/test_treasury.py.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from cinis.services.treasury_service import TreasuryService


@dataclass
class _FakeTreasury:
    TreasuryID: int
    Balance: Decimal


class _FakeRepository:
    def __init__(self, starting_balance: Decimal):
        self.treasury = _FakeTreasury(TreasuryID=1, Balance=starting_balance)
        self.category_ids = {
            "RESIDENT_INCOME": 1,
            "BUILDING_MAINTENANCE": 2,
        }
        self.added_entries = []

    def get_treasury(self, city_id: int):
        return self.treasury

    def get_category_type_id(self, code: str) -> int:
        return self.category_ids[code]

    def add_ledger_entry(
        self,
        treasury_id,
        category_type_id,
        entry_date,
        amount,
        simulation_run_id=None,
        simulation_tick_id=None,
    ):
        self.added_entries.append(
            {
                "treasury_id": treasury_id,
                "category_type_id": category_type_id,
                "entry_date": entry_date,
                "amount": amount,
                "simulation_run_id": simulation_run_id,
                "simulation_tick_id": simulation_tick_id,
            }
        )


def test_get_balance_returns_current_balance():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    assert service.get_balance(city_id=1) == Decimal("10000.00")


def test_record_income_entry_increases_balance():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    result = service.record_ledger_entry(
        city_id=1,
        category_code="RESIDENT_INCOME",
        amount=Decimal("1252.06"),
        entry_date=date(2026, 2, 1),
    )

    assert result.new_balance == Decimal("11252.06")
    assert repo.treasury.Balance == Decimal("11252.06")


def test_record_expense_entry_decreases_balance():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    result = service.record_ledger_entry(
        city_id=1,
        category_code="BUILDING_MAINTENANCE",
        amount=Decimal("-20.00"),
        entry_date=date(2026, 2, 1),
    )

    assert result.new_balance == Decimal("9980.00")


def test_record_ledger_entry_stages_a_ledger_row():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    service.record_ledger_entry(
        city_id=1,
        category_code="RESIDENT_INCOME",
        amount=Decimal("500.00"),
        entry_date=date(2026, 3, 1),
    )

    assert len(repo.added_entries) == 1
    assert repo.added_entries[0]["amount"] == Decimal("500.00")
    assert repo.added_entries[0]["treasury_id"] == 1


def test_multiple_entries_accumulate_correctly():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    service.record_ledger_entry(1, "RESIDENT_INCOME", Decimal("1000.00"), date(2026, 2, 1))
    service.record_ledger_entry(1, "BUILDING_MAINTENANCE", Decimal("-40.00"), date(2026, 2, 1))
    result = service.record_ledger_entry(
        1, "RESIDENT_INCOME", Decimal("1000.00"), date(2026, 3, 1)
    )

    assert result.new_balance == Decimal("11960.00")
    assert len(repo.added_entries) == 3


def test_unknown_category_code_raises():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    with pytest.raises(KeyError):
        service.record_ledger_entry(
            1, "NOT_A_REAL_CATEGORY", Decimal("100.00"), date(2026, 2, 1)
        )


def test_trace_ids_default_to_none_and_are_passed_to_the_repository():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    service.record_ledger_entry(1, "RESIDENT_INCOME", Decimal("10.00"), date(2026, 3, 1))
    service.record_ledger_entry(
        1,
        "RESIDENT_INCOME",
        Decimal("10.00"),
        date(2026, 3, 2),
        simulation_run_id=7,
        simulation_tick_id=3,
    )

    assert [(e["simulation_run_id"], e["simulation_tick_id"]) for e in repo.added_entries] == [
        (None, None),
        (7, 3),
    ]


def test_partial_trace_raises_before_anything_is_staged():
    repo = _FakeRepository(starting_balance=Decimal("10000.00"))
    service = TreasuryService(repo)

    with pytest.raises(ValueError, match="together"):
        service.record_ledger_entry(
            1, "RESIDENT_INCOME", Decimal("10.00"), date(2026, 3, 1), simulation_tick_id=3
        )

    assert repo.added_entries == []
    assert repo.treasury.Balance == Decimal("10000.00")
