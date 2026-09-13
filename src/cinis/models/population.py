"""
Population domain models mapping to the 0005 migration. Per ADR-0005,
population "needs" are modeled as categories here (e.g. eventually a
NeedType concept); this M2 slice only covers group structure and the
generic ScenarioParameter mechanism used to keep rates configurable.
Wiring needs to real inventory/resources is Milestone 3+ scope.
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


class PopulationGroupType(Base):
    __tablename__ = "PopulationGroupType"

    PopulationGroupTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"PopulationGroupType(Code={self.Code!r})"


class PopulationGroup(Base):
    __tablename__ = "PopulationGroup"
    __table_args__ = (
        CheckConstraint("Count >= 0", name="CK_PopulationGroup_Count_NonNegative"),
    )

    PopulationGroupID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CityID: Mapped[int] = mapped_column(ForeignKey("City.CityID"), nullable=False)
    PopulationGroupTypeID: Mapped[int] = mapped_column(
        ForeignKey("PopulationGroupType.PopulationGroupTypeID"), nullable=False
    )
    Count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    city: Mapped["City"] = relationship()  # noqa: F821
    group_type: Mapped["PopulationGroupType"] = relationship()

    def __repr__(self) -> str:
        return (
            f"PopulationGroup(CityID={self.CityID!r}, "
            f"PopulationGroupTypeID={self.PopulationGroupTypeID!r}, Count={self.Count!r})"
        )


class ScenarioParameter(Base):
    __tablename__ = "ScenarioParameter"

    ScenarioParameterID: Mapped[int] = mapped_column(Integer, primary_key=True)
    ScenarioID: Mapped[int] = mapped_column(ForeignKey("Scenario.ScenarioID"), nullable=False)
    ParameterKey: Mapped[str] = mapped_column(String(100), nullable=False)
    ParameterValue: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    scenario: Mapped["Scenario"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"ScenarioParameter(ScenarioID={self.ScenarioID!r}, "
            f"ParameterKey={self.ParameterKey!r}, ParameterValue={self.ParameterValue!r})"
        )
