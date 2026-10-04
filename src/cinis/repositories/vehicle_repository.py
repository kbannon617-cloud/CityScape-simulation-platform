"""
Vehicle repository. Catalog, current city vehicle counts, and
get_or_create_city_vehicle (Step 4.6b) - the one write path this
repository supports, used by VehicleOrderingService to add newly
ordered vehicles to a city's count.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.vehicle import BuildingVehicleRequirement, CityVehicle, VehicleType


class VehicleTypeNotFoundError(RuntimeError):
    """Raised when a requested vehicle type code has not been seeded."""


class VehicleRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_vehicle_type(self, code: str) -> VehicleType:
        vehicle_type = (
            self._session.query(VehicleType).filter(VehicleType.Code == code).one_or_none()
        )
        if vehicle_type is None:
            raise VehicleTypeNotFoundError(f"No VehicleType found for Code={code!r}")
        return vehicle_type

    def get_or_create_city_vehicle(self, city_id: int, vehicle_type_id: int) -> CityVehicle:
        """Return the CityVehicle row for (city, vehicle type), creating it
        at zero count first if it doesn't exist yet. Mirrors
        ProductionRepository.get_or_create_building /
        InventoryRepository.get_or_create_inventory."""
        vehicle = (
            self._session.query(CityVehicle)
            .filter(CityVehicle.CityID == city_id, CityVehicle.VehicleTypeID == vehicle_type_id)
            .one_or_none()
        )
        if vehicle is None:
            vehicle = CityVehicle(CityID=city_id, VehicleTypeID=vehicle_type_id, Count=0)
            self._session.add(vehicle)
            self._session.flush()
        return vehicle

    def get_city_vehicles(self, city_id: int) -> dict[str, int]:
        """Return {vehicle_type_code: count} for every vehicle a city has."""
        rows = (
            self._session.query(VehicleType.Code, CityVehicle.Count)
            .join(CityVehicle, CityVehicle.VehicleTypeID == VehicleType.VehicleTypeID)
            .filter(CityVehicle.CityID == city_id)
            .all()
        )
        return {code: count for code, count in rows}

    def get_vehicle_requirement_for_building_type(
        self, building_type_code: str
    ) -> BuildingVehicleRequirement | None:
        """Return the vehicle requirement for a building type, or None if
        that building type doesn't need any vehicle (most don't)."""
        from cinis.models.production import BuildingType

        return (
            self._session.query(BuildingVehicleRequirement)
            .join(
                BuildingType,
                BuildingType.BuildingTypeID == BuildingVehicleRequirement.BuildingTypeID,
            )
            .filter(BuildingType.Code == building_type_code)
            .one_or_none()
        )
