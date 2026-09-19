"""
Vehicle repository. Read-only for this milestone step, matching
ProductionRepository's initial scope - catalog and current city vehicle
counts, not yet a vehicle-ordering execution service.
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
