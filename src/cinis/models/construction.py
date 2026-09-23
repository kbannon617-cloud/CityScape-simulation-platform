"""
Construction Projects domain models mapping to the 0023 migration.
See ADR-0011 for the design (order-time cost/material deduction,
completion-time building effect, month-boundary-tick-driven progress,
and the service-layer concurrent-project limit).
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base

STATUS_IN_PROGRESS = "InProgress"
STATUS_COMPLETE = "Complete"


class ConstructionProject(Base):
    """One building order. Maps to migration 0023."""

    __tablename__ = "ConstructionProject"
    __table_args__ = (
        CheckConstraint("BuildingsOrdered >= 1", name="CK_ConstructionProject_BuildingsOrdered_Positive"),
        CheckConstraint(
            "AdjustedDurationMonths >= 1",
            name="CK_ConstructionProject_AdjustedDurationMonths_Positive",
        ),
        CheckConstraint(
            "MonthsElapsed >= 0", name="CK_ConstructionProject_MonthsElapsed_NonNegative"
        ),
        CheckConstraint("Status IN ('InProgress', 'Complete')", name="CK_ConstructionProject_Status"),
        CheckConstraint(
            "(Status = 'InProgress' AND CompletedSimulationDate IS NULL) OR "
            "(Status = 'Complete' AND CompletedSimulationDate IS NOT NULL)",
            name="CK_ConstructionProject_Completed_Consistency",
        ),
    )

    ConstructionProjectID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False)
    BuildingTypeID: Mapped[int] = mapped_column(
        ForeignKey("BuildingType.BuildingTypeID"), nullable=False
    )
    BuildingsOrdered: Mapped[int] = mapped_column(Integer, nullable=False)
    OrderSimulationDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # Snapshotted at order time - see migration header. Not recomputed if
    # the BuildingType catalog changes later.
    TotalConstructionCost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    TotalTimberRequired: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    TotalStoneRequired: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    AdjustedDurationMonths: Mapped[int] = mapped_column(Integer, nullable=False)
    MonthsElapsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    Status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_IN_PROGRESS)
    CompletedSimulationDate: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    building_type: Mapped["BuildingType"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"ConstructionProject(ConstructionProjectID={self.ConstructionProjectID!r}, "
            f"CityID={self.CityID!r}, Status={self.Status!r}, "
            f"MonthsElapsed={self.MonthsElapsed!r}/{self.AdjustedDurationMonths!r})"
        )
