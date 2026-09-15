"""
Production repository. Read-only for this milestone step - it exposes
the catalog (what building types exist, what a city currently has built,
what each building type consumes/produces). Actual monthly production
execution (consuming inputs, producing outputs into a real city
inventory) is a deliberately separate next step, once CityInventory
exists.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.production import Building, BuildingType, ProductionFlow


class BuildingTypeNotFoundError(RuntimeError):
    """Raised when a requested building type code has not been seeded."""


class ProductionRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_building_type(self, code: str) -> BuildingType:
        building_type = (
            self._session.query(BuildingType).filter(BuildingType.Code == code).one_or_none()
        )
        if building_type is None:
            raise BuildingTypeNotFoundError(f"No BuildingType found for Code={code!r}")
        return building_type

    def get_city_buildings(self, city_id: int) -> dict[str, int]:
        """Return {building_type_code: count} for every building a city has."""
        rows = (
            self._session.query(BuildingType.Code, Building.Count)
            .join(Building, Building.BuildingTypeID == BuildingType.BuildingTypeID)
            .filter(Building.CityID == city_id)
            .all()
        )
        return {code: count for code, count in rows}

    def get_flows_for_building_type(self, building_type_code: str) -> list[ProductionFlow]:
        """Return every ProductionFlow (input and output) for a building type."""
        return (
            self._session.query(ProductionFlow)
            .join(BuildingType, BuildingType.BuildingTypeID == ProductionFlow.BuildingTypeID)
            .filter(BuildingType.Code == building_type_code)
            .all()
        )
