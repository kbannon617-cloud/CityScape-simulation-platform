"""
Importing this package ensures every model class is registered with the
shared declarative Base before any relationship() with a string reference
(e.g. PopulationGroup.city -> "City") needs to resolve.
"""

from cinis.models.base import Base
from cinis.models.geography import City, Region, World
from cinis.models.population import PopulationGroup, PopulationGroupType, ScenarioParameter
from cinis.models.reference import Currency, UnitOfMeasure
from cinis.models.simulation import Scenario, Simulation, SimulationRun

__all__ = [
    "Base",
    "City",
    "Region",
    "World",
    "PopulationGroup",
    "PopulationGroupType",
    "ScenarioParameter",
    "Currency",
    "UnitOfMeasure",
    "Scenario",
    "Simulation",
    "SimulationRun",
]
