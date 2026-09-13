"""
Integration tests for essential needs and labor capability, run against
real SQL Server with the actual seeded 100 Adult / 20 Child CityScape data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.needs_repository import NeedsRepository
from cinis.repositories.population_repository import PopulationRepository
from cinis.services.needs_service import NeedsService
from cinis.services.population_service import PopulationService


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


def test_daily_need_totals_match_seeded_placeholder_rates(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, _ = cityscape_and_baseline_ids
    needs_repo = NeedsRepository(sqlalchemy_session)
    population_repo = PopulationRepository(sqlalchemy_session)
    service = NeedsService(needs_repo, population_repo)

    totals = {t.need_type_code: t for t in service.calculate_daily_need_totals(city_id)}

    assert set(totals.keys()) == {"FOOD", "HEATING", "BASIC_GOODS"}

    # 100 Adult * 1.0 + 20 Child * 0.5 = 110 KG food/day
    assert totals["FOOD"].total_quantity == pytest.approx(110.0)
    assert totals["FOOD"].unit_code == "KG"

    # 100 * 0.8 + 20 * 0.4 = 88 KG heating/day
    assert totals["HEATING"].total_quantity == pytest.approx(88.0)

    # 100 * 0.2 + 20 * 0.1 = 22 EA basic goods/day
    assert totals["BASIC_GOODS"].total_quantity == pytest.approx(22.0)
    assert totals["BASIC_GOODS"].unit_code == "EA"


def test_available_labor_with_real_seeded_full_participation_rate(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    repo = PopulationRepository(sqlalchemy_session)
    service = PopulationService(repo)

    # Seeded rate is 100% participation, seeded Adult count is 100.
    assert service.calculate_available_labor(city_id, scenario_id) == 100


def test_available_labor_respects_a_reduced_participation_rate(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    """Temporarily lowers the participation rate inside a savepoint to
    prove the rate is actually read and applied, not just always 100%
    because the seeded value happens to be 100%."""
    city_id, scenario_id = cityscape_and_baseline_ids
    repo = PopulationRepository(sqlalchemy_session)
    service = PopulationService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            "UPDATE dbo.ScenarioParameter SET ParameterValue = 75 "
            "WHERE ScenarioID = ? AND ParameterKey = 'AdultLaborParticipationRatePercent'",
            scenario_id,
        )
        sqlalchemy_session.flush()

        # 100 adults * 75% = 75
        assert service.calculate_available_labor(city_id, scenario_id) == 75
    finally:
        savepoint.rollback()

    assert service.calculate_available_labor(city_id, scenario_id) == 100
