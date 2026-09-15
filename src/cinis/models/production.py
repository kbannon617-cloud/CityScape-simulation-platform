"""
Production domain models mapping to the 0011 migration.

BuildingType deliberately has no Monthly Output / Output Resource fields -
ProductionFlow is the single source of truth for what a building consumes
or produces, per the migration's own header notes.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class BuildingType(Base):
    __tablename__ = "BuildingType"

    BuildingTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    Category: Mapped[str] = mapped_column(String(50), nullable=False)
    BuildingSubType: Mapped[str] = mapped_column(String(50), nullable=False)
    Subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    HousingCapacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    WorkersPerBuilding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ConstructionCost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    MonthlyMaintenance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    VehicleTypeCode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    VehicleCapacityPerBuilding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    VehiclesAssignedPerBuilding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    TimberRequiredPerBuilding: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    StoneRequiredPerBuilding: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    StorageCapacityShared: Mapped[int | None] = mapped_column(Integer, nullable=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    Size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    RequiredTechID: Mapped[int | None] = mapped_column(Integer, nullable=True)
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"BuildingType(Code={self.Code!r}, Name={self.Name!r})"


class Building(Base):
    __tablename__ = "Building"
    __table_args__ = (
        CheckConstraint("Count >= 0", name="CK_Building_Count_NonNegative"),
    )

    BuildingID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False)
    BuildingTypeID: Mapped[int] = mapped_column(
        ForeignKey("BuildingType.BuildingTypeID"), nullable=False
    )
    Count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    building_type: Mapped["BuildingType"] = relationship()

    def __repr__(self) -> str:
        return (
            f"Building(CityID={self.CityID!r}, "
            f"BuildingTypeID={self.BuildingTypeID!r}, Count={self.Count!r})"
        )


class ProductionFlow(Base):
    __tablename__ = "ProductionFlow"
    __table_args__ = (
        CheckConstraint("FlowType IN ('Input', 'Output')", name="CK_ProductionFlow_FlowType"),
        CheckConstraint(
            "UnitsPerBuildingPerMonth >= 0", name="CK_ProductionFlow_UnitsNonNegative"
        ),
    )

    ProductionFlowID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    BuildingTypeID: Mapped[int] = mapped_column(
        ForeignKey("BuildingType.BuildingTypeID"), nullable=False
    )
    FlowType: Mapped[str] = mapped_column(String(10), nullable=False)
    ResourceID: Mapped[int] = mapped_column(ForeignKey("Resource.ResourceID"), nullable=False)
    UnitsPerBuildingPerMonth: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    FlowRole: Mapped[str | None] = mapped_column(String(30), nullable=True)
    RequiredTechID: Mapped[int | None] = mapped_column(Integer, nullable=True)
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    building_type: Mapped["BuildingType"] = relationship()
    resource: Mapped["Resource"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"ProductionFlow(Code={self.Code!r}, FlowType={self.FlowType!r}, "
            f"UnitsPerBuildingPerMonth={self.UnitsPerBuildingPerMonth!r})"
        )
