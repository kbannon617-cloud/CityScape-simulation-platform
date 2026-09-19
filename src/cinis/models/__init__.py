"""
Importing this package ensures every model class is registered with the
shared declarative Base before any relationship() with a string reference
(e.g. PopulationGroup.city -> "City") needs to resolve.
"""

from cinis.models.base import Base
from cinis.models.economy import Treasury, TreasuryCategoryType, TreasuryLedgerEntry
from cinis.models.geography import City, Region, World
from cinis.models.inventory import CityInventory, InventoryLedgerEntry, Resource
from cinis.models.market import Market, MarketResourcePrice, MarketTransaction
from cinis.models.needs import NeedConsumptionRate, NeedType
from cinis.models.population import PopulationGroup, PopulationGroupType, ScenarioParameter
from cinis.models.production import Building, BuildingType, ProductionFlow
from cinis.models.reference import Currency, UnitOfMeasure
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.models.vehicle import BuildingVehicleRequirement, CityVehicle, TransportMode, VehicleType

__all__ = [
    "Base",
    "City",
    "Region",
    "World",
    "NeedType",
    "NeedConsumptionRate",
    "PopulationGroup",
    "PopulationGroupType",
    "ScenarioParameter",
    "Currency",
    "UnitOfMeasure",
    "Scenario",
    "Simulation",
    "SimulationRun",
    "Treasury",
    "TreasuryCategoryType",
    "TreasuryLedgerEntry",
    "Resource",
    "CityInventory",
    "InventoryLedgerEntry",
    "BuildingType",
    "Building",
    "ProductionFlow",
    "VehicleType",
    "TransportMode",
    "BuildingVehicleRequirement",
    "CityVehicle",
    "Market",
    "MarketResourcePrice",
    "MarketTransaction",
]
