"""
Integration test proving PopulationService.apply_monthly_aging works
end-to-end: real repository, real Session, real SQL Server. Uses a
savepoint to temporarily inflate CityScape's child count high enough to
see non-zero aging, then rolls back - the real seeded values (100/20) are
never permanently mutated, per the ADR-0004 test-hygiene convention.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.population_repository import PopulationRepository
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


def test_apply_monthly_aging_end_to_end_with_real_repository(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    city_id, scenario_id = cityscape_and_baseline_ids
    repo = PopulationRepository(sqlalchemy_session)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        # Inflate the child count so 1.5% produces a real, visible result
        # (the actual seeded 20 would floor to 0 - already proven
        # separately in test_population.py's rules-level coverage).
        child_group = repo.get_group(city_id, "CHILD")
        child_group.Count = 1000
        sqlalchemy_session.flush()

        service = PopulationService(repo)
        result = service.apply_monthly_aging(city_id, scenario_id)
        sqlalchemy_session.flush()

        assert result.aged_count == 15
        assert result.new_child_count == 985

        # Confirm it actually persisted to the database within this
        # transaction, not just mutated the in-memory object.
        cursor = sqlalchemy_session.connection().connection.cursor()
        cursor.execute(
            """
            SELECT pg.Count FROM dbo.PopulationGroup pg
            JOIN dbo.PopulationGroupType pgt
                ON pgt.PopulationGroupTypeID = pg.PopulationGroupTypeID
            WHERE pg.CityID = ? AND pgt.Code = 'CHILD'
            """,
            city_id,
        )
        assert cursor.fetchone()[0] == 985
    finally:
        savepoint.rollback()

    # Confirm the rollback actually restored the real seeded value.
    restored = repo.get_group(city_id, "CHILD")
    assert restored.Count == 20


def test_apply_monthly_aging_with_real_seeded_placeholder_data_ages_zero(
    sqlalchemy_session, cityscape_and_baseline_ids
):
    """With the actual (unvalidated placeholder) seed data - 20 children
    at 1.5%/month - zero people age this month. This is expected per
    calculate_aged_count's floor behavior, not a bug."""
    city_id, scenario_id = cityscape_and_baseline_ids
    repo = PopulationRepository(sqlalchemy_session)
    service = PopulationService(repo)

    savepoint = sqlalchemy_session.begin_nested()
    try:
        result = service.apply_monthly_aging(city_id, scenario_id)
        assert result.aged_count == 0
        assert result.new_child_count == 20
        assert result.new_adult_count == 100
    finally:
        savepoint.rollback()
