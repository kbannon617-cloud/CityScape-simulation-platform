"""Simulation control models mapping to Document 5's Simulation, Scenario,
and SimulationRun tables."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UnicodeText,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cinis.models.base import Base


class Simulation(Base):
    __tablename__ = "Simulation"

    SimulationID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    Description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    scenarios: Mapped[list["Scenario"]] = relationship(back_populates="simulation")

    def __repr__(self) -> str:
        return f"Simulation(SimulationID={self.SimulationID!r}, Name={self.Name!r})"


class Scenario(Base):
    __tablename__ = "Scenario"

    ScenarioID: Mapped[int] = mapped_column(Integer, primary_key=True)
    SimulationID: Mapped[int] = mapped_column(
        ForeignKey("Simulation.SimulationID"), nullable=False
    )
    # NULL = base scenario. Non-NULL = child scenario inheriting base
    # context and storing delta overrides only (see ADR-0003).
    ParentScenarioID: Mapped[int | None] = mapped_column(
        ForeignKey("Scenario.ScenarioID"), nullable=True
    )
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    Description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    simulation: Mapped["Simulation"] = relationship(back_populates="scenarios")
    parent_scenario: Mapped["Scenario | None"] = relationship(remote_side=[ScenarioID])
    runs: Mapped[list["SimulationRun"]] = relationship(back_populates="scenario")

    def __repr__(self) -> str:
        return f"Scenario(ScenarioID={self.ScenarioID!r}, Name={self.Name!r})"


class SimulationRun(Base):
    __tablename__ = "SimulationRun"
    __table_args__ = (
        CheckConstraint(
            "Status IN ('Active', 'Completed', 'Failed', 'Cancelled')",
            name="CK_SimulationRun_Status",
        ),
    )

    SimulationRunID: Mapped[int] = mapped_column(Integer, primary_key=True)
    ScenarioID: Mapped[int] = mapped_column(ForeignKey("Scenario.ScenarioID"), nullable=False)
    StartSimulationDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    CurrentSimulationDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # BIGINT: tick counts grow across a run's lifetime (see ADR-0003).
    CurrentSimulationTickID: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    Status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="runs")

    def __repr__(self) -> str:
        return (
            f"SimulationRun(SimulationRunID={self.SimulationRunID!r}, "
            f"Status={self.Status!r})"
        )


class SimulationEvent(Base):
    """Append-only event log for a run (the EVENTS leg of Document 5's
    CURRENT STATE + EVENTS + SNAPSHOTS pattern). Maps to migration 0019."""

    __tablename__ = "SimulationEvent"
    __table_args__ = (
        CheckConstraint(
            "SimulationTickID >= 1",
            name="CK_SimulationEvent_SimulationTickID_Positive",
        ),
        CheckConstraint(
            "Payload IS NULL OR ISJSON(Payload) = 1",
            name="CK_SimulationEvent_Payload_IsJson",
        ),
    )

    SimulationEventID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    SimulationRunID: Mapped[int] = mapped_column(
        ForeignKey("SimulationRun.SimulationRunID"), nullable=False
    )
    # Per-run counter: only meaningful together with SimulationRunID.
    SimulationTickID: Mapped[int] = mapped_column(BigInteger, nullable=False)
    SimulationDate: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    CityID: Mapped[int | None] = mapped_column(ForeignKey("City.CityID"), nullable=True)
    EventType: Mapped[str] = mapped_column(String(50), nullable=False)
    Description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # JSON text (sorted keys, so identical inputs give identical text).
    Payload: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return (
            f"SimulationEvent(SimulationEventID={self.SimulationEventID!r}, "
            f"EventType={self.EventType!r})"
        )
