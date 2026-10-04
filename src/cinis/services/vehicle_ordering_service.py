"""
Vehicle ordering service: a command, called on demand (not a tick step),
like ConstructionService.order_project.

Simpler than Construction: there is no duration/queue concept anywhere
in the schema or the design-concept workbook for vehicles - an order
takes effect immediately. Materials (Timber/Stone) are deducted through
InventoryService; the vehicle count is incremented immediately via
VehicleRepository, no ConstructionProject-style tracking row.

No treasury cost: the real VehicleType catalog has no price column (only
Timber/Stone requirements and ongoing BaseMaintenancePerVehicle, which is
not yet deducted anywhere - the same pre-existing maintenance gap already
flagged for Construction's BuildingType.MonthlyMaintenance). A
VEHICLE_ORDER_COST TreasuryCategoryType is already seeded for future use
but is not written here, since there is no price to apply.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from cinis.models.vehicle import CityVehicle
from cinis.repositories.vehicle_repository import VehicleRepository
from cinis.services.inventory_service import InventoryService

TIMBER_RESOURCE_CODE = "R-004"
STONE_RESOURCE_CODE = "R-003"


class VehicleOrderingService:
    def __init__(self, repository: VehicleRepository, inventory_service: InventoryService):
        self._repository = repository
        self._inventory_service = inventory_service

    def order_vehicles(
        self,
        city_id: int,
        vehicle_type_code: str,
        vehicles_ordered: int,
        order_date: datetime.date,
        simulation_run_id: int | None = None,
        simulation_tick_id: int | None = None,
    ) -> CityVehicle:
        """Order vehicles_ordered vehicles of vehicle_type_code for
        city_id. Deducts Timber/Stone immediately and increments the
        city's vehicle count immediately - no construction duration.

        Raises ValueError if vehicles_ordered is not at least 1,
        InsufficientInventoryError if Timber or Stone would go negative.
        """
        if vehicles_ordered < 1:
            raise ValueError(f"vehicles_ordered must be at least 1, got {vehicles_ordered}")

        vehicle_type = self._repository.get_vehicle_type(vehicle_type_code)
        quantity = Decimal(vehicles_ordered)
        total_timber = vehicle_type.TimberRequiredPerVehicle * quantity
        total_stone = vehicle_type.StoneRequiredPerVehicle * quantity

        if total_timber > 0:
            self._inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=self._inventory_service.get_resource_id(TIMBER_RESOURCE_CODE),
                amount=-total_timber,
                entry_date=order_date,
                notes=f"Vehicle order: {vehicles_ordered}x {vehicle_type_code}.",
                simulation_run_id=simulation_run_id,
                simulation_tick_id=simulation_tick_id,
            )
        if total_stone > 0:
            self._inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=self._inventory_service.get_resource_id(STONE_RESOURCE_CODE),
                amount=-total_stone,
                entry_date=order_date,
                notes=f"Vehicle order: {vehicles_ordered}x {vehicle_type_code}.",
                simulation_run_id=simulation_run_id,
                simulation_tick_id=simulation_tick_id,
            )

        vehicle = self._repository.get_or_create_city_vehicle(
            city_id, vehicle_type.VehicleTypeID
        )
        vehicle.Count += vehicles_ordered
        return vehicle
