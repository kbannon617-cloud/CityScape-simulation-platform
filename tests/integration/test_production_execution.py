"""
Integration tests for ProductionService.execute_monthly_production against
real SQL Server, using the actual seeded CityScape data (1 Wheat Farm,
3 Cottages, 100 Adult labor at 100% participation, 100 Wheat / 100 Timber
opening stock).
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.inventory_repository import InventoryRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.repositories.production_repository import ProductionRepository
from cinis.services.inventory_service import InventoryService
from cinis.services.production_service import ProductionService


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
        """
        SELECT sc.ScenarioID FROM dbo.Scenario sc
        JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
        WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline'
        """
    )
    scenario_id = cursor.fetchone()[0]
    return city_id, scenario_id


def _build_service(session):
    return ProductionService(
        ProductionRepository(session),
        InventoryService(InventoryRepository(session)),
        PopulationRepository(session),
    )


def test_real_wheat_farm_production_run_increases_wheat_inventory(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        results = service.execute_monthly_production(
            city_id, scenario_id, datetime.date(2026, 2, 1)
        )
        sqlalchemy_session.flush()

        by_code = {r.building_type_code: r for r in results}

        # B-001 Cottage: no production flows, zero workers.
        assert by_code["B-001"].staffed_count == 3
        assert by_code["B-001"].outputs_produced == {}

        # B-002 Wheat Farm: real production, 1 building, 100 Wheat/month.
        wheat_farm = by_code["B-002"]
        assert wheat_farm.staffed_count == 1
        assert wheat_farm.skipped_reason is None
        assert wheat_farm.outputs_produced == {"R-001": Decimal("100")}

        # Actual inventory: 100 seeded + 100 produced = 200.
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            """
            SELECT ci.Quantity FROM dbo.CityInventory ci
            JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID
            WHERE ci.CityID = ? AND r.Code = 'R-001'
            """,
            city_id,
        )
        assert Decimal(str(cursor.fetchone()[0])) == Decimal("200.0000")
    finally:
        savepoint.rollback()

    # Confirm rollback restored the real seeded value.
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute(
        """
        SELECT ci.Quantity FROM dbo.CityInventory ci
        JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID
        WHERE ci.CityID = ? AND r.Code = 'R-001'
        """,
        city_id,
    )
    assert Decimal(str(cursor.fetchone()[0])) == Decimal("100.0000")


def test_saw_mill_with_real_labor_but_zero_timber_is_skipped(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    """Temporarily adds a Saw Mill (real building type, currently owned
    count 0) inside a savepoint, to exercise the input-shortage skip path
    for real - CityScape's actual seed data has no Saw Mill, so this
    scenario doesn't occur naturally."""
    city_id, scenario_id = cityscape_and_baseline_ids
    service = _build_service(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute("SELECT BuildingTypeID FROM dbo.BuildingType WHERE Code = 'B-009'")
        saw_mill_type_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO dbo.Building (CityID, BuildingTypeID, Count) VALUES (?, ?, 1)",
            city_id,
            saw_mill_type_id,
        )
        sqlalchemy_session.flush()

        # CityScape has 100 real Timber - drain it to 0 within this
        # savepoint so the Saw Mill genuinely cannot get its 100 Timber input.
        cursor.execute(
            """
            UPDATE dbo.CityInventory SET Quantity = 0
            WHERE CityID = ? AND ResourceID = (SELECT ResourceID FROM dbo.Resource WHERE Code = 'R-004')
            """,
            city_id,
        )
        sqlalchemy_session.flush()

        results = service.execute_monthly_production(
            city_id, scenario_id, datetime.date(2026, 2, 1)
        )
        saw_mill_result = next(r for r in results if r.building_type_code == "B-009")

        assert saw_mill_result.skipped_reason == "Insufficient input inventory"
        assert saw_mill_result.staffed_count == 1  # labor was available and spent
    finally:
        savepoint.rollback()

    # Confirm the temporary Saw Mill and Timber drain never persisted.
    cursor = sqlalchemy_session.connection().connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM dbo.Building b
        JOIN dbo.BuildingType bt ON bt.BuildingTypeID = b.BuildingTypeID
        WHERE b.CityID = ? AND bt.Code = 'B-009'
        """,
        city_id,
    )
    assert cursor.fetchone()[0] == 0
