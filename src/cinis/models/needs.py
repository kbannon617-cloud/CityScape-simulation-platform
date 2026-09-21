"""
Essential needs models mapping to the 0007 migration. Per ADR-0005, needs
are modeled as categories with per-person consumption rates. NeedTypeResource
(migration 0021, ADR-0010) is the link from a need category to the Resource
Catalog items that can satisfy it, with a consumption priority.
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
    UniqueConstraint,
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


class NeedTypeResource(Base):
    """Which resources satisfy a need type, in consumption-priority order
    (1 is consumed first). Maps to migration 0021; see ADR-0010."""

    __tablename__ = "NeedTypeResource"
    __table_args__ = (
        UniqueConstraint(
            "NeedTypeID", "ResourceID", name="UQ_NeedTypeResource_NeedType_Resource"
        ),
        UniqueConstraint(
            "NeedTypeID", "ConsumptionPriority", name="UQ_NeedTypeResource_NeedType_Priority"
        ),
        CheckConstraint(
            "ConsumptionPriority >= 1",
            name="CK_NeedTypeResource_ConsumptionPriority_Positive",
        ),
    )

    NeedTypeResourceID: Mapped[int] = mapped_column(Integer, primary_key=True)
    NeedTypeID: Mapped[int] = mapped_column(ForeignKey("NeedType.NeedTypeID"), nullable=False)
    ResourceID: Mapped[int] = mapped_column(ForeignKey("Resource.ResourceID"), nullable=False)
    ConsumptionPriority: Mapped[int] = mapped_column(Integer, nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    need_type: Mapped["NeedType"] = relationship()
    resource: Mapped["Resource"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"NeedTypeResource(NeedTypeID={self.NeedTypeID!r}, "
            f"ResourceID={self.ResourceID!r}, "
            f"ConsumptionPriority={self.ConsumptionPriority!r})"
        )
