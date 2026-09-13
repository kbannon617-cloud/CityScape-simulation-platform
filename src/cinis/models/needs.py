"""
Essential needs models mapping to the 0007 migration. Per ADR-0005, needs
are modeled as categories with per-person consumption rates only - not
wired to real Resource Catalog items or city inventory (Economy/Inventory
domain, Milestone 3+).
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class NeedType(Base):
    __tablename__ = "NeedType"

    NeedTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"NeedType(Code={self.Code!r})"


class NeedConsumptionRate(Base):
    __tablename__ = "NeedConsumptionRate"
    __table_args__ = (
        CheckConstraint(
            "QuantityPerPersonPerDay >= 0",
            name="CK_NeedConsumptionRate_QuantityNonNegative",
        ),
    )

    NeedConsumptionRateID: Mapped[int] = mapped_column(Integer, primary_key=True)
    PopulationGroupTypeID: Mapped[int] = mapped_column(
        ForeignKey("PopulationGroupType.PopulationGroupTypeID"), nullable=False
    )
    NeedTypeID: Mapped[int] = mapped_column(ForeignKey("NeedType.NeedTypeID"), nullable=False)
    QuantityPerPersonPerDay: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    UnitOfMeasureID: Mapped[int] = mapped_column(
        ForeignKey("UnitOfMeasure.UnitOfMeasureID"), nullable=False
    )
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    group_type: Mapped["PopulationGroupType"] = relationship()  # noqa: F821
    need_type: Mapped["NeedType"] = relationship()
    unit_of_measure: Mapped["UnitOfMeasure"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"NeedConsumptionRate(PopulationGroupTypeID={self.PopulationGroupTypeID!r}, "
            f"NeedTypeID={self.NeedTypeID!r}, "
            f"QuantityPerPersonPerDay={self.QuantityPerPersonPerDay!r})"
        )
