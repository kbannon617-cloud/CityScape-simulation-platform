"""
Integration tests for ConstructionService.order_project against real SQL
Server, using the actual seeded CityScape/Cinis Baseline data (1 Wheat
Farm, 3 Cottages, 100 Timber / 100 Wheat opening stock, the three
construction ScenarioParameter rows from migration 0024).

Stone (R-003) intentionally has ZERO opening stock (migration 0014 seeds
only Wheat and Timber) - matches the sparse-seeding convention, a missing
row means zero. Tests that order a building requiring Stone top it up
first via _seed_resource_stock, inside their own SAVEPOINT, so the real
seed data is never touched.

Safe by construction: order_project() never commits (like every other
service in this codebase - the caller owns the transaction boundary), so
each test runs inside one SAVEPOINT via sqlalchemy_session.begin_nested()
and rolls it back in a finally block. Nothing here shares a session across
multiple internal commits, which is what caused the Step 4.4c incident.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.models.construction import STATUS_IN_PROGRESS
from cinis.repositories.construction_repository import ConstructionRepository
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.repositories.treasury_repository import TreasuryRepository
from cinis.services.construction_service import (
    ConstructionService,
    MaxActiveConstructionProjectsExceededError,
)
from cinis.services.inventory_service import InsufficientInventoryError, InventoryService
from cinis.services.treasury_service import TreasuryService

D = Decimal
ORDER_DATE = datetime.date(1880, 2, 1)


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cityscape_and_baseline_ids(sqlalchemy_session):
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute("SELECT CityID FROM dbo.City WHERE Name = 'CityScape'")
    city_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT sc.ScenarioID FROM dbo.Scenario sc "
        "JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID "
        "WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'"
    )
    scenario_id = cursor.fetchone()[0]
    return city_id, scenario_id


def _build_service(session):
    return ConstructionService(
        ConstructionRepository(session),
        TreasuryService(TreasuryRepository(session)),
        InventoryService(InventoryRepository(session)),
        ProductionRepository(session),
        PopulationRepository(session),
    )


def _seed_resource_stock(sqlalchemy_session, city_id, resource_code, amount):
    """Give a resource additional opening stock within the current
    SAVEPOINT. Real seed data (migration 0014) intentionally leaves
    Stone at zero, so tests that order a building requiring Stone need
    this before calling order_project. Rolled back with everything else
    in the test's finally block."""
    resource_id = InventoryService(InventoryRepository(sqlalchemy_session)).get_resource_id(
        resource_code
    )
    InventoryService(InventoryRepository(sqlalchemy_session)).record_ledger_entry(
        city_id=city_id,
        resource_id=resource_id,
        amount=Decimal(str(amount)),
        entry_date=datetime.date(1880, 1, 1),
        notes="Test-seeded stock.",
    )
    sqlalchemy_session.flush()


def test_order_project_deducts_treasury_and_materials_and_creates_the_row(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(
            city_id
        )
        starting_timber = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(
            city_id, "R-004"
        )
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)

        project = service.order_project(
            city_id=city_id,
            scenario_id=scenario_id,
            building_type_code="B-002",  # real seed: cost 750, timber 50, stone 25
            buildings_ordered=1,
            order_date=ORDER_DATE,
        )
        sqlalchemy_session.flush()

        assert project.Status == STATUS_IN_PROGRESS
        assert project.TotalConstructionCost == D("750.0000")
        assert project.TotalTimberRequired == D("50.0000")
        assert project.AdjustedDurationMonths == 8  # 750/100 budget, no completed crews

        new_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(city_id)
        new_timber = InventoryService(InventoryRepository(sqlalchemy_session)).get_quantity(
            city_id, "R-004"
        )
        assert new_balance == starting_balance - D("750.0000")
        assert new_timber == starting_timber - D("50.0000")
    finally:
        savepoint.rollback()


def test_a_second_order_is_refused_while_one_is_in_progress(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)
        service.order_project(city_id, scenario_id, "B-002", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        with pytest.raises(MaxActiveConstructionProjectsExceededError):
            service.order_project(city_id, scenario_id, "B-002", 1, ORDER_DATE)
    finally:
        savepoint.rollback()


def test_insufficient_timber_is_refused_and_nothing_is_left_staged(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(
            city_id
        )
        # 100 Timber seeded; ordering 3 Wheat Farms needs 150.
        with pytest.raises(InsufficientInventoryError):
            service.order_project(city_id, scenario_id, "B-002", 3, ORDER_DATE)

        # No treasury deduction should have been committed either, since
        # materials are checked before cost is deducted.
        balance_after = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(
            city_id
        )
        assert balance_after == starting_balance

        count = (
            ConstructionRepository(sqlalchemy_session).count_active_projects(city_id)
        )
        assert count == 0
    finally:
        savepoint.rollback()


def test_zero_cost_construction_crew_writes_no_treasury_entry(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        starting_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(
            city_id
        )
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)

        project = service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        assert project.TotalConstructionCost == D("0.0000")
        new_balance = TreasuryService(TreasuryRepository(sqlalchemy_session)).get_balance(
            city_id
        )
        assert new_balance == starting_balance  # unchanged: zero-amount write skipped
    finally:
        savepoint.rollback()


def test_raising_the_limit_parameter_permits_a_second_concurrent_project(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            "UPDATE dbo.ScenarioParameter SET ParameterValue = 2 "
            "WHERE ScenarioID = ? AND ParameterKey = 'MaxActiveConstructionProjectsPerCity'",
            scenario_id,
        )
        _seed_resource_stock(sqlalchemy_session, city_id, "R-003", 1000)

        service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)
        sqlalchemy_session.flush()
        # Second concurrent order now succeeds with the limit raised to 2.
        service.order_project(city_id, scenario_id, "B-007", 1, ORDER_DATE)
        sqlalchemy_session.flush()

        assert ConstructionRepository(sqlalchemy_session).count_active_projects(city_id) == 2
    finally:
        savepoint.rollback()
