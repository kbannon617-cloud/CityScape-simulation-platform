"""
Vehicles & Logistics models (Infrastructure & Assets domain, ADR-0005)
mapping to the 0015 migration.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class VehicleType(Base):
    __tablename__ = "VehicleType"

    VehicleTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    Type: Mapped[str] = mapped_column(String(30), nullable=False)
    Class: Mapped[str] = mapped_column(String(30), nullable=False)
    TimberRequiredPerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    StoneRequiredPerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    BaseMaintenancePerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    MaximumPerBuilding: Mapped[int | None] = mapped_column(Integer, nullable=True)
    IncludedVehicleRule: Mapped[str | None] = mapped_column(String(200), nullable=True)
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    Size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    RequiredTechCode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"VehicleType(Code={self.Code!r}, Type={self.Type!r})"


class TransportMode(Base):
    __tablename__ = "TransportMode"

    TransportModeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    ModeName: Mapped[str] = mapped_column(String(30), nullable=False)
    TransportFamily: Mapped[str] = mapped_column(String(30), nullable=False)
    VehicleTypeID: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.VehicleTypeID"), nullable=False
    )
    Size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    GoodsCapacityPerVehiclePerMonth: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    TripsPerMonth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    TeamstersPerVehicle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    BaseMaintenancePerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    GoodsCapacityPerTeamsterPerMonth: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    TimberRequiredPerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    StoneRequiredPerVehicle: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=0
    )
    MaximumVehiclesPerDepot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    InfrastructureRequired: Mapped[str | None] = mapped_column(String(50), nullable=True)
    RequiredTechCode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    Status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    Notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    vehicle_type: Mapped["VehicleType"] = relationship()

    def __repr__(self) -> str:
        return f"TransportMode(Code={self.Code!r}, ModeName={self.ModeName!r})"


class BuildingVehicleRequirement(Base):
    __tablename__ = "BuildingVehicleRequirement"

    BuildingVehicleRequirementID: Mapped[int] = mapped_column(Integer, primary_key=True)
    BuildingTypeID: Mapped[int] = mapped_column(
        ForeignKey("BuildingType.BuildingTypeID"), nullable=False
    )
    VehicleTypeID: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.VehicleTypeID"), nullable=False
    )
    CapacityPerBuilding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    IncludedPerBuilding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    building_type: Mapped["BuildingType"] = relationship()  # noqa: F821
    vehicle_type: Mapped["VehicleType"] = relationship()

    def __repr__(self) -> str:
        return (
            f"BuildingVehicleRequirement(BuildingTypeID={self.BuildingTypeID!r}, "
            f"VehicleTypeID={self.VehicleTypeID!r})"
        )


class CityVehicle(Base):
    __tablename__ = "CityVehicle"
    __table_args__ = (
        CheckConstraint("Count >= 0", name="CK_CityVehicle_Count_NonNegative"),
    )

    CityVehicleID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False)
    VehicleTypeID: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.VehicleTypeID"), nullable=False
    )
    Count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    vehicle_type: Mapped["VehicleType"] = relationship()

    def __repr__(self) -> str:
        return (
            f"CityVehicle(CityID={self.CityID!r}, VehicleTypeID={self.VehicleTypeID!r}, "
            f"Count={self.Count!r})"
        )
