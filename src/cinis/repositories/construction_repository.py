"""
Construction repository. Isolates all SQL access for ConstructionProject.

Scope (Step 4.5b): counting/reading a city's active projects and creating
new ones (order_project). Advancing MonthsElapsed and completing a project
is Step 4.5c's tick step.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.models.construction import STATUS_IN_PROGRESS, ConstructionProject


class ConstructionRepository:
    def __init__(self, session: Session):
        self._session = session

    def count_active_projects(self, city_id: int) -> int:
        """How many of this city's projects are currently InProgress."""
        return (
            self._session.query(ConstructionProject)
            .filter(
                ConstructionProject.CityID == city_id,
                ConstructionProject.Status == STATUS_IN_PROGRESS,
            )
            .count()
        )

    def get_active_projects(self, city_id: int) -> list[ConstructionProject]:
        """This city's InProgress projects, oldest first (deterministic
        processing order for the tick step)."""
        return (
            self._session.query(ConstructionProject)
            .filter(
                ConstructionProject.CityID == city_id,
                ConstructionProject.Status == STATUS_IN_PROGRESS,
            )
            .order_by(ConstructionProject.ConstructionProjectID)
            .all()
        )

    def create_project(
        self,
        city_id: int,
        building_type_id: int,
        buildings_ordered: int,
        order_date: datetime.date,
        total_construction_cost: Decimal,
        total_timber_required: Decimal,
        total_stone_required: Decimal,
        adjusted_duration_months: int,
    ) -> ConstructionProject:
        """Create and stage a new InProgress project. Does not commit; the
        caller owns the transaction boundary."""
        project = ConstructionProject(
            CityID=city_id,
            BuildingTypeID=building_type_id,
            BuildingsOrdered=buildings_ordered,
            OrderSimulationDate=order_date,
            TotalConstructionCost=total_construction_cost,
            TotalTimberRequired=total_timber_required,
            TotalStoneRequired=total_stone_required,
            AdjustedDurationMonths=adjusted_duration_months,
        )
        self._session.add(project)
        return project
