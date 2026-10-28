"""
M5 Step 5.2: builder for the fully isolated, synthetic Test city that the
M5 vertical-slice tests run against.

Why a builder instead of reusing Step 4.7's setup: that city (3 children,
no buildings, no market, no prices) proves the pipeline does not crash but
cannot prove it does the RIGHT thing - 3 children x 1.5% floors to 0 aged,
Production has no buildings to run, and there is no Market row or price
rows for MarketService. The slice needs a city where every step has
something observable to do. Step 4.7's test is deliberately left untouched
(M5 decision); this module is the second copy of that setup pattern, grown
to what the slice needs.

SAFETY: everything created here is Test-prefixed or FK'd to a Test
city/scenario, and committed for real (the engine opens its own sessions
per tick, so setup data must be committed - the proven M4 Step 4.7
pattern). conftest.py's cleanup removes all of it at session end. The real
CityScape city and the Cinis Baseline scenario are never read for writing,
never modified, and never passed to the engine.

This is test infrastructure only (not src/): nothing here ships.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal

from cinis.models.population import PopulationGroup, PopulationGroupType
from cinis.models.simulation import Scenario, Simulation, SimulationRun
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.services.inventory_service import InventoryService

# The day before a month boundary: one tick from here lands on the first of
# the next month, the only kind of tick on which Aging, Production,
# Construction and Snapshot all run (ADR-0009).
SLICE_START_DATE = datetime.date(1880, 1, 31)

DEFAULT_SCENARIO_PARAMETERS: dict[str, float] = {
    "ChildToAdultMonthlyAgingRatePercent": 1.5,
    "AdultLaborParticipationRatePercent": 100.0,
    "MonthlyConstructionBudget": 100.0,
    "ConstructionBonusPerCompletedCrew": 0.0005,
    "MaxActiveConstructionProjectsPerCity": 1,
}

# 2 Wheat Farms (output-only flow) + 1 Saw Mill (consumes Timber, outputs
# Lumber): needs 2x5 + 25 = 35 workers.
DEFAULT_BUILDINGS: dict[str, int] = {"B-002": 2, "B-009": 1}

# Wheat, Timber, Stone. Lumber (R-005) is deliberately absent: it exists
# only once the Saw Mill produces it (sparse seeding - missing means zero).
DEFAULT_OPENING_STOCK: dict[str, Decimal] = {
    "R-001": Decimal("1000"),
    "R-004": Decimal("1000"),
    "R-003": Decimal("1000"),
}

# Explicit fixed prices for the Test scenario, so trade arithmetic in the
# slice test is exact and independent of any later balancing of the real
# Cinis Baseline prices. Wheat and Lumber.
DEFAULT_RESOURCE_PRICES: dict[str, Decimal] = {
    "R-001": Decimal("2.0000"),
    "R-005": Decimal("3.0000"),
}


@dataclass(frozen=True)
class IsolatedCity:
    """Identifiers for everything the tests need to find again."""

    suffix: str
    city_id: int
    simulation_id: int
    scenario_id: int
    run_id: int
    treasury_id: int
    market_id: int
    start_date: datetime.date


def build_isolated_city(
    session_factory,
    *,
    label: str = "Slice",
    start_date: datetime.date = SLICE_START_DATE,
    adults: int = 100,
    children: int = 200,
    buildings: dict[str, int] | None = None,
    opening_stock: dict[str, Decimal] | None = None,
    treasury_balance: Decimal = Decimal("1000.00"),
    resource_prices: dict[str, Decimal] | None = None,
    scenario_parameters: dict[str, float] | None = None,
) -> IsolatedCity:
    """Create and commit one isolated Test city and everything it needs.

    Passing None for a dict argument selects the slice default; pass {} to
    seed none of that kind. A group, building or stock of zero is not
    seeded at all (sparse seeding: a missing row means zero).

    All-or-nothing: a single commit at the end, rollback on any error.
    Returns the identifiers; the run is at tick 0 on start_date, Active.
    """
    buildings = DEFAULT_BUILDINGS if buildings is None else buildings
    opening_stock = DEFAULT_OPENING_STOCK if opening_stock is None else opening_stock
    resource_prices = DEFAULT_RESOURCE_PRICES if resource_prices is None else resource_prices
    scenario_parameters = (
        DEFAULT_SCENARIO_PARAMETERS if scenario_parameters is None else scenario_parameters
    )

    suffix = uuid.uuid4().hex[:8]
    session = session_factory()
    try:
        cursor = session.connection().connection.cursor()

        cursor.execute(
            "INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)",
            f"TestWorld{label}-{suffix}",
        )
        world_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
            world_id, f"TestRegion{label}-{suffix}",
        )
        region_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) "
            "OUTPUT INSERTED.CityID VALUES (?, ?, 0)",
            region_id, f"TestCity{label}-{suffix}",
        )
        city_id = cursor.fetchone()[0]

        # Treasury has no get-or-create path, so the row must exist before
        # TreasuryService will work. Reuse the real seeded Standard Currency.
        cursor.execute("SELECT CurrencyID FROM dbo.Currency WHERE Code = 'STD'")
        currency_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.Treasury (CityID, CurrencyID, Balance) "
            "OUTPUT INSERTED.TreasuryID VALUES (?, ?, ?)",
            city_id, currency_id, treasury_balance,
        )
        treasury_id = cursor.fetchone()[0]

        # MarketService needs a Market row per city; nothing creates one
        # for a new city, and the real city's was seeded by a migration.
        cursor.execute(
            "INSERT INTO dbo.Market (CityID) OUTPUT INSERTED.MarketID VALUES (?)", city_id
        )
        market_id = cursor.fetchone()[0]

        simulation = Simulation(Name=f"TestSimulation{label}-{suffix}")
        session.add(simulation)
        session.flush()
        scenario = Scenario(
            SimulationID=simulation.SimulationID, Name=f"TestScenario{label}-{suffix}"
        )
        session.add(scenario)
        session.flush()

        for key, value in scenario_parameters.items():
            cursor.execute(
                "INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue) "
                "VALUES (?, ?, ?)",
                scenario.ScenarioID, key, value,
            )

        run = SimulationRun(
            ScenarioID=scenario.ScenarioID,
            StartSimulationDate=start_date,
            CurrentSimulationDate=start_date,
        )
        session.add(run)
        session.flush()

        for code, count in (("ADULT", adults), ("CHILD", children)):
            if count == 0:
                continue
            group_type_id = (
                session.query(PopulationGroupType.PopulationGroupTypeID)
                .filter(PopulationGroupType.Code == code)
                .scalar()
            )
            session.add(
                PopulationGroup(CityID=city_id, PopulationGroupTypeID=group_type_id, Count=count)
            )

        production_repository = ProductionRepository(session)
        for building_type_code, count in buildings.items():
            if count == 0:
                continue
            building_type = production_repository.get_building_type(building_type_code)
            building = production_repository.get_or_create_building(
                city_id, building_type.BuildingTypeID
            )
            building.Count = count

        inventory_service = InventoryService(InventoryRepository(session))
        opening_date = start_date - datetime.timedelta(days=1)
        for resource_code, amount in opening_stock.items():
            if amount == 0:
                continue
            inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=inventory_service.get_resource_id(resource_code),
                amount=amount,
                entry_date=opening_date,
                notes="Test isolated city opening stock.",
            )

        for resource_code, unit_price in resource_prices.items():
            cursor.execute(
                "INSERT INTO dbo.MarketResourcePrice (ScenarioID, ResourceID, CurrencyID, UnitPrice) "
                "VALUES (?, ?, ?, ?)",
                scenario.ScenarioID, inventory_service.get_resource_id(resource_code),
                currency_id, unit_price,
            )

        # Read the generated IDs before committing: with the default
        # expire_on_commit=True, touching ORM attributes afterwards would
        # trigger refresh queries, and the result should not depend on how
        # the caller configured its sessionmaker.
        result = IsolatedCity(
            suffix=suffix,
            city_id=city_id,
            simulation_id=simulation.SimulationID,
            scenario_id=scenario.ScenarioID,
            run_id=run.SimulationRunID,
            treasury_id=treasury_id,
            market_id=market_id,
            start_date=start_date,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
