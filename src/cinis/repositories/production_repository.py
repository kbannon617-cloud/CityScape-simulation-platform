"""
Production repository. Exposes the catalog (what building types exist,
what a city currently has built, what each building type
consumes/produces) and get_or_create_building, the one write path this
repository supports - used by ConstructionService.advance_projects
(Step 4.5c) to add newly completed buildings to a city's count.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.production import Building, BuildingType, ProductionFlow


class BuildingTypeNotFoundError(RuntimeError):
    """Raised when a requested building type code has not been seeded."""


class ProductionRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_or_create_building(self, city_id: int, building_type_id: int) -> Building:
        """Return the Building row for (city, building type), creating it
        at zero count first if it doesn't exist yet. Used by
        ConstructionService.advance_projects before incrementing Count,
        so a city's first building of a given type always has a real row
        to add to - mirrors InventoryRepository.get_or_create_inventory."""
        building = (
            self._session.query(Building)
            .filter(Building.CityID == city_id, Building.BuildingTypeID == building_type_id)
            .one_or_none()
        )
        if building is None:
            building = Building(CityID=city_id, BuildingTypeID=building_type_id, Count=0)
            self._session.add(building)
            self._session.flush()
        return building

    def get_building_type(self, code: str) -> BuildingType:
        building_type = (
            self._session.query(BuildingType).filter(BuildingType.Code == code).one_or_none()
        )
        if building_type is None:
            raise BuildingTypeNotFoundError(f"No BuildingType found for Code={code!r}")
        return building_type

    def get_building_type_by_id(self, building_type_id: int) -> BuildingType:
        """Look up a BuildingType by its primary key. Used where a caller
        already has a BuildingTypeID (e.g. from a ConstructionProject) and
        needs the catalog row - e.g. the Construction tick step, to put a
        human-readable Code in a ConstructionCompleted event payload."""
        building_type = self._session.get(BuildingType, building_type_id)
        if building_type is None:
            raise BuildingTypeNotFoundError(f"No BuildingType found for BuildingTypeID={building_type_id!r}")
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

    def get_city_buildings_with_type(self, city_id: int) -> list[tuple[Building, BuildingType]]:
        """Return (Building, BuildingType) pairs for a city, ordered by
        BuildingType.Code - the deterministic processing order
        ProductionService relies on for its first-come-first-served
        labor allocation."""
        return (
            self._session.query(Building, BuildingType)
            .join(BuildingType, BuildingType.BuildingTypeID == Building.BuildingTypeID)
            .filter(Building.CityID == city_id, Building.Count > 0)
            .order_by(BuildingType.Code)
            .all()
        )

    def get_flows_for_building_type(self, building_type_code: str) -> list[ProductionFlow]:
        """Return every ProductionFlow (input and output) for a building type."""
        return (
            self._session.query(ProductionFlow)
            .join(BuildingType, BuildingType.BuildingTypeID == ProductionFlow.BuildingTypeID)
            .filter(BuildingType.Code == building_type_code)
            .all()
        )
