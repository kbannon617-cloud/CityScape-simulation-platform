"""
Inventory domain models mapping to the 0011 and 0013 migrations.
CityInventory is current state (one row per City/Resource pair, with a
hard non-negative CHECK per Document 7); InventoryLedgerEntry is the
append-only history it's derived from, mirroring the Treasury pattern.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class Resource(Base):
    __tablename__ = "Resource"
    __table_args__ = (
        CheckConstraint(
            "PopulationFoodStatus IN ('Yes', 'No', 'Future')",
            name="CK_Resource_PopulationFoodStatus",
        ),
    )

    ResourceID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    ResourceClass: Mapped[str] = mapped_column(String(50), nullable=False)
    PopulationFoodStatus: Mapped[str] = mapped_column(String(10), nullable=False, default="No")
    TrackedInStorage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    UnitOfMeasureID: Mapped[int] = mapped_column(
        ForeignKey("UnitOfMeasure.UnitOfMeasureID"), nullable=False
    )
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    unit_of_measure: Mapped["UnitOfMeasure"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"Resource(Code={self.Code!r}, Name={self.Name!r})"


class CityInventory(Base):
    __tablename__ = "CityInventory"
    __table_args__ = (
        CheckConstraint("Quantity >= 0", name="CK_CityInventory_Quantity_NonNegative"),
    )

    CityInventoryID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False)
    ResourceID: Mapped[int] = mapped_column(ForeignKey("Resource.ResourceID"), nullable=False)
    Quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    resource: Mapped["Resource"] = relationship()

    def __repr__(self) -> str:
        return (
            f"CityInventory(CityID={self.CityID!r}, ResourceID={self.ResourceID!r}, "
            f"Quantity={self.Quantity!r})"
        )


class InventoryLedgerEntry(Base):
    __tablename__ = "InventoryLedgerEntry"

    InventoryLedgerEntryID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    CityInventoryID: Mapped[int] = mapped_column(
        ForeignKey("CityInventory.CityInventoryID"), nullable=False
    )
    EntryDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    Amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city_inventory: Mapped["CityInventory"] = relationship()

    def __repr__(self) -> str:
        return (
            f"InventoryLedgerEntry(CityInventoryID={self.CityInventoryID!r}, "
            f"Amount={self.Amount!r}, EntryDate={self.EntryDate!r})"
        )

