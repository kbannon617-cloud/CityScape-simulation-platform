"""
Treasury repository. Isolates all SQL access for Treasury/TreasuryLedgerEntry,
per Document 6's layering.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.models.economy import Treasury, TreasuryCategoryType, TreasuryLedgerEntry


class TreasuryNotFoundError(RuntimeError):
    """Raised when a city has no Treasury row. Should never happen once
    the 0010 seed migration has run for a city, but checked explicitly
    rather than propagating a silent None."""


class TreasuryCategoryTypeNotFoundError(RuntimeError):
    """Raised when a requested treasury category code has not been seeded."""


class TreasuryRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_treasury(self, city_id: int) -> Treasury:
        treasury = (
            self._session.query(Treasury).filter(Treasury.CityID == city_id).one_or_none()
        )
        if treasury is None:
            raise TreasuryNotFoundError(f"No Treasury found for CityID={city_id}")
        return treasury

    def get_category_type_id(self, code: str) -> int:
        category = (
            self._session.query(TreasuryCategoryType)
            .filter(TreasuryCategoryType.Code == code)
            .one_or_none()
        )
        if category is None:
            raise TreasuryCategoryTypeNotFoundError(
                f"No TreasuryCategoryType found for Code={code!r}"
            )
        return category.TreasuryCategoryTypeID

    def add_ledger_entry(
        self,
        treasury_id: int,
        category_type_id: int,
        entry_date: datetime.date,
        amount: Decimal,
    ) -> TreasuryLedgerEntry:
        """Create and stage a new ledger entry. Does not commit - the
        caller (TreasuryService, via its own caller) owns the transaction
        boundary."""
        entry = TreasuryLedgerEntry(
            TreasuryID=treasury_id,
            TreasuryCategoryTypeID=category_type_id,
            EntryDate=entry_date,
            Amount=amount,
        )
        self._session.add(entry)
        return entry
