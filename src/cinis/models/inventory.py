"""
Inventory domain reference data mapping to the 0011 migration.
Resource is the catalog of what can exist in a city's inventory; the
actual city-level stockpile tracking (CityInventory) is a separate,
not-yet-built piece.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
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
