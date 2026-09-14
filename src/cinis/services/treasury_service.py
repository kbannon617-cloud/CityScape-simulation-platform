"""
Treasury service: the only place that should ever change Treasury.Balance.
Every balance change goes through record_ledger_entry so the append-only
TreasuryLedgerEntry history and the current-state Balance never drift
apart - the ledger is the source of truth, Balance is a running total
derived from it.

Standalone and callable now, ahead of any tick engine - Milestone 4's
SimulationEngine will call this for construction order-time deductions,
monthly maintenance, etc. once it exists.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from cinis.repositories.treasury_repository import TreasuryRepository


@dataclass(frozen=True)
class LedgerEntryResult:
    new_balance: Decimal
    entry_amount: Decimal
    category_code: str


class TreasuryService:
    def __init__(self, repository: TreasuryRepository):
        self._repository = repository

    def get_balance(self, city_id: int) -> Decimal:
        return self._repository.get_treasury(city_id).Balance

    def record_ledger_entry(
        self,
        city_id: int,
        category_code: str,
        amount: Decimal,
        entry_date: datetime.date,
    ) -> LedgerEntryResult:
        """Record a signed ledger entry and update the running balance.

        amount is signed: positive increases the balance (income),
        negative decreases it (expense). Does not commit; the caller
        owns the transaction boundary, consistent with the pattern
        already used in PopulationService.
        """
        treasury = self._repository.get_treasury(city_id)
        category_type_id = self._repository.get_category_type_id(category_code)

        self._repository.add_ledger_entry(
            treasury_id=treasury.TreasuryID,
            category_type_id=category_type_id,
            entry_date=entry_date,
            amount=amount,
        )

        treasury.Balance = treasury.Balance + amount

        return LedgerEntryResult(
            new_balance=treasury.Balance,
            entry_amount=amount,
            category_code=category_code,
        )
