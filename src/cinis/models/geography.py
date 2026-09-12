"""Geography models mapping to Document 5's World, Region, City tables."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class World(Base):
    __tablename__ = "World"

    WorldID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    regions: Mapped[list["Region"]] = relationship(back_populates="world")

    def __repr__(self) -> str:
        return f"World(WorldID={self.WorldID!r}, Name={self.Name!r})"


class Region(Base):
    __tablename__ = "Region"

    RegionID: Mapped[int] = mapped_column(Integer, primary_key=True)
    WorldID: Mapped[int] = mapped_column(ForeignKey("World.WorldID"), nullable=False)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    world: Mapped["World"] = relationship(back_populates="regions")
    cities: Mapped[list["City"]] = relationship(back_populates="region")

    def __repr__(self) -> str:
        return f"Region(RegionID={self.RegionID!r}, Name={self.Name!r})"


class City(Base):
    __tablename__ = "City"

    CityID: Mapped[int] = mapped_column(Integer, primary_key=True)
    RegionID: Mapped[int] = mapped_column(ForeignKey("Region.RegionID"), nullable=False)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    IsPrimaryActive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    region: Mapped["Region"] = relationship(back_populates="cities")

    def __repr__(self) -> str:
        return (
            f"City(CityID={self.CityID!r}, Name={self.Name!r}, "
            f"IsPrimaryActive={self.IsPrimaryActive!r})"
        )
