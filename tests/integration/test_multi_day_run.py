"""
Step 4.7: proof that the full default tick-step pipeline (Aging,
Production, Construction, NeedsConsumption, Snapshot) runs correctly end
to end over many real ticks through the real SimulationEngine.

Deliberately NOT run against the real CityScape city or Cinis Baseline
scenario - every step's dependencies_factory is overridden (via
dataclasses.replace) to redirect city_id to a fully isolated Test city,
so this never touches live seeded data. The engine commits for real each
tick (same proven-safe pattern as test_engine_transactions.py: a real
session_factory, not one session shared across multiple ticks), but
everything written is Test-prefixed or FK'd to the Test city/scenario,
cleaned up by conftest.py afterward.

Real end-to-end validation against LIVE seeded data remains M6's job, per
the Step 4.4c incident notes - this test proves the pipeline works, on
synthetic data built specifically so it can safely commit.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cinis.config.settings import load_database_settings
from cinis.models.population import PopulationGroup, PopulationGroupType
from cinis.models.simulation import CitySnapshot, Scenario, Simulation, SimulationRun
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.services.inventory_service import InventoryService
from cinis.simulation.aging_step import build_aging_step_dependencies, make_aging_step
from cinis.simulation.construction_step import (
    build_construction_step_dependencies,
    make_construction_step,
)
from cinis.simulation.engine import SimulationEngine
from cinis.simulation.needs_step import build_needs_step_dependencies, make_needs_consumption_step
from cinis.simulation.production_step import build_production_step_dependencies, make_production_step
from cinis.simulation.snapshot_step import build_snapshot_step_dependencies, make_snapshot_step

START_DATE = datetime.date(1880, 1, 15)
RUN_DAYS = 65  # crosses two month boundaries: Feb 1 and Mar 1

SCENARIO_PARAMETERS = {
    "ChildToAdultMonthlyAgingRatePercent": 1.5,
    "AdultLaborParticipationRatePercent": 100.0,
    "MonthlyConstructionBudget": 100.0,
    "ConstructionBonusPerCompletedCrew": 0.0005,
    "MaxActiveConstructionProjectsPerCity": 1,
}


def _redirect(default_factory, city_id):
    """Wrap a step's default dependencies_factory so it targets an
    isolated Test city instead of the real primary-active city, without
    touching get_primary_active_city or any real-data flag."""

    def factory(session):
        return dataclasses.replace(default_factory(session), city_id=city_id)

    return factory


@pytest.fixture(scope="module")
def session_factory(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    yield sessionmaker(bind=engine)
    engine.dispose()


def _setup_isolated_city(session_factory) -> tuple[int, int]:
    """One-off setup, committed for real: a Test World/Region/City with
    minimal population and stock, a Test Simulation/Scenario carrying its
    own ScenarioParameter rows, and a Test SimulationRun. Returns
    (city_id, run_id)."""
    session = session_factory()
    try:
        suffix = uuid.uuid4().hex[:8]
        cursor = session.connection().connection.cursor()

        cursor.execute(
            "INSERT INTO dbo.World (Name) OUTPUT INSERTED.WorldID VALUES (?)", f"TestWorld-{suffix}"
        )
        world_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.Region (WorldID, Name) OUTPUT INSERTED.RegionID VALUES (?, ?)",
            world_id, f"TestRegion-{suffix}",
        )
        region_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) "
            "OUTPUT INSERTED.CityID VALUES (?, ?, 0)",
            region_id, f"TestCity-{suffix}",
        )
        city_id = cursor.fetchone()[0]

        # Treasury has no get-or-create path (unlike CityInventory,
        # Building, CityVehicle) - a row must exist before
        # TreasuryService.get_balance/record_ledger_entry will work. Reuse
        # the real seeded Standard Currency (migration 0003).
        cursor.execute("SELECT CurrencyID FROM dbo.Currency WHERE Code = 'STD'")
        currency_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO dbo.Treasury (CityID, CurrencyID, Balance) VALUES (?, ?, ?)",
            city_id, currency_id, Decimal("1000.00"),
        )

        simulation = Simulation(Name=f"TestSimulationMultiDay-{suffix}")
        session.add(simulation)
        session.flush()
        scenario = Scenario(SimulationID=simulation.SimulationID, Name=f"TestScenarioMultiDay-{suffix}")
        session.add(scenario)
        session.flush()
        for key, value in SCENARIO_PARAMETERS.items():
            cursor.execute(
                "INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue) "
                "VALUES (?, ?, ?)",
                scenario.ScenarioID, key, value,
            )
        run = SimulationRun(
            ScenarioID=scenario.ScenarioID,
            StartSimulationDate=START_DATE,
            CurrentSimulationDate=START_DATE,
        )
        session.add(run)
        session.flush()

        for code, count in (("ADULT", 10), ("CHILD", 3)):
            group_type_id = (
                session.query(PopulationGroupType.PopulationGroupTypeID)
                .filter(PopulationGroupType.Code == code)
                .scalar()
            )
            session.add(PopulationGroup(CityID=city_id, PopulationGroupTypeID=group_type_id, Count=count))

        inventory_service = InventoryService(InventoryRepository(session))
        setup_date = START_DATE - datetime.timedelta(days=1)
        for resource_code, amount in (("R-001", "500"), ("R-004", "500"), ("R-003", "500")):
            inventory_service.record_ledger_entry(
                city_id=city_id,
                resource_id=inventory_service.get_resource_id(resource_code),
                amount=Decimal(amount),
                entry_date=setup_date,
                notes="Test multi-day run opening stock.",
            )

        session.commit()
        return city_id, run.SimulationRunID
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _build_isolated_steps(city_id):
    return (
        make_aging_step(_redirect(build_aging_step_dependencies, city_id)),
        make_production_step(_redirect(build_production_step_dependencies, city_id)),
        make_construction_step(_redirect(build_construction_step_dependencies, city_id)),
        make_needs_consumption_step(_redirect(build_needs_step_dependencies, city_id)),
        make_snapshot_step(_redirect(build_snapshot_step_dependencies, city_id)),
    )


def test_a_65_day_run_completes_through_every_step_without_error(session_factory):
    city_id, run_id = _setup_isolated_city(session_factory)
    engine = SimulationEngine(session_factory, _build_isolated_steps(city_id))

    results = [engine.run_tick(run_id) for _ in range(RUN_DAYS)]

    session = session_factory()
    try:
        cursor = session.connection().connection.cursor()
        cursor.execute(
            "SELECT CurrentSimulationDate, CurrentSimulationTickID, Status "
            "FROM dbo.SimulationRun WHERE SimulationRunID = ?",
            run_id,
        )
        run_date, run_tick, status = cursor.fetchone()
        assert (run_date, run_tick, status) == (
            START_DATE + datetime.timedelta(days=RUN_DAYS),
            RUN_DAYS,
            "Active",
        )

        boundary_results = [r for r in results if r.is_month_boundary]
        assert len(boundary_results) == 2  # Feb 1 and Mar 1
        assert all("Snapshot" in r.executed_steps for r in boundary_results)
        assert all("Snapshot" not in r.executed_steps for r in results if not r.is_month_boundary)

        snapshots = (
            session.query(CitySnapshot)
            .filter(CitySnapshot.SimulationRunID == run_id)
            .order_by(CitySnapshot.SimulationTickID)
            .all()
        )
        assert len(snapshots) == 2
        first_payload = json.loads(snapshots[0].Payload)
        assert first_payload["AdultCount"] >= 10
        assert "TreasuryBalance" in first_payload
        assert "R-001" in first_payload["Inventory"]

        cursor.execute(
            "SELECT MIN(Count) FROM dbo.PopulationGroup WHERE CityID = ?", city_id
        )
        assert cursor.fetchone()[0] >= 0
    finally:
        session.close()
