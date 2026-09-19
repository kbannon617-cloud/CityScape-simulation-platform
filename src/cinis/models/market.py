"""
Markets and Transactions domain models mapping to the 0017 migration.
MarketTransaction realizes both domains at once, per the migration's own
header notes - no other transaction type exists in MVP scope.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class Market(Base):
    __tablename__ = "Market"

    MarketID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False, unique=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"Market(CityID={self.CityID!r})"


class MarketResourcePrice(Base):
    __tablename__ = "MarketResourcePrice"
    __table_args__ = (
        CheckConstraint("UnitPrice > 0", name="CK_MarketResourcePrice_UnitPrice_Positive"),
    )

    MarketResourcePriceID: Mapped[int] = mapped_column(Integer, primary_key=True)
    ScenarioID: Mapped[int] = mapped_column(ForeignKey("Scenario.ScenarioID"), nullable=False)
    ResourceID: Mapped[int] = mapped_column(ForeignKey("Resource.ResourceID"), nullable=False)
    CurrencyID: Mapped[int] = mapped_column(ForeignKey("Currency.CurrencyID"), nullable=False)
    UnitPrice: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    resource: Mapped["Resource"] = relationship()  # noqa: F821
    currency: Mapped["Currency"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"MarketResourcePrice(ScenarioID={self.ScenarioID!r}, "
            f"ResourceID={self.ResourceID!r}, UnitPrice={self.UnitPrice!r})"
        )


class MarketTransaction(Base):
    __tablename__ = "MarketTransaction"
    __table_args__ = (
        CheckConstraint(
            "TransactionType IN ('Buy', 'Sell')", name="CK_MarketTransaction_TransactionType"
        ),
        CheckConstraint("Quantity > 0", name="CK_MarketTransaction_Quantity_Positive"),
        CheckConstraint("UnitPrice > 0", name="CK_MarketTransaction_UnitPrice_Positive"),
    )

    MarketTransactionID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    MarketID: Mapped[int] = mapped_column(ForeignKey("Market.MarketID"), nullable=False)
    ResourceID: Mapped[int] = mapped_column(ForeignKey("Resource.ResourceID"), nullable=False)
    TransactionType: Mapped[str] = mapped_column(String(10), nullable=False)
    Quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    UnitPrice: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    TotalValue: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    TransactionDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    market: Mapped["Market"] = relationship()
    resource: Mapped["Resource"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"MarketTransaction(TransactionType={self.TransactionType!r}, "
            f"Quantity={self.Quantity!r}, TotalValue={self.TotalValue!r})"
        )
