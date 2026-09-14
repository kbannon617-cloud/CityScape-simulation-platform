"""
Economy domain models mapping to the 0009 migration. Treasury is current
state (1:1 with City); TreasuryLedgerEntry is the append-only history it
is derived from, per Document 5's CURRENT STATE + EVENTS + SNAPSHOTS
pattern.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class TreasuryCategoryType(Base):
    __tablename__ = "TreasuryCategoryType"

    TreasuryCategoryTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"TreasuryCategoryType(Code={self.Code!r})"


class Treasury(Base):
    __tablename__ = "Treasury"

    TreasuryID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False, unique=True)
    CurrencyID: Mapped[int] = mapped_column(ForeignKey("Currency.CurrencyID"), nullable=False)
    Balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    currency: Mapped["Currency"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"Treasury(CityID={self.CityID!r}, Balance={self.Balance!r})"


class TreasuryLedgerEntry(Base):
    __tablename__ = "TreasuryLedgerEntry"

    TreasuryLedgerEntryID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    TreasuryID: Mapped[int] = mapped_column(ForeignKey("Treasury.TreasuryID"), nullable=False)
    TreasuryCategoryTypeID: Mapped[int] = mapped_column(
        ForeignKey("TreasuryCategoryType.TreasuryCategoryTypeID"), nullable=False
    )
    EntryDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    Amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    treasury: Mapped["Treasury"] = relationship()
    category_type: Mapped["TreasuryCategoryType"] = relationship()

    def __repr__(self) -> str:
        return (
            f"TreasuryLedgerEntry(TreasuryID={self.TreasuryID!r}, "
            f"Amount={self.Amount!r}, EntryDate={self.EntryDate!r})"
        )
