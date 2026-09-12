"""
Integration test proving CityRepository.get_primary_active_city() actually
works end-to-end against a real SQL Server database - not just that the
model classes import cleanly, but that a real SQLAlchemy Session querying
through them returns the real seeded CityScape row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cinis.config.settings import load_database_settings
from cinis.repositories.city_repository import CityNotFoundError, CityRepository


@pytest.fixture(scope="module")
def sqlalchemy_session(connection):
    # Reuse the same connection settings as the shared pyodbc fixture,
    # but through a real SQLAlchemy engine/session, since that is what
    # CityRepository is written against.
    settings = load_database_settings()
    engine = create_engine(settings.to_sqlalchemy_url())
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_get_primary_active_city_returns_cityscape(sqlalchemy_session):
    repo = CityRepository(sqlalchemy_session)

    city = repo.get_primary_active_city()

    assert city.Name == "CityScape"
    assert city.IsPrimaryActive is True


def test_get_primary_active_city_raises_when_none_exists(sqlalchemy_session):
    """Temporarily clears IsPrimaryActive inside a savepoint, proving the
    error path fires for real, then rolls back so real seed data is
    untouched - no permanent mutation, matching the ADR-0004 test-hygiene
    convention even though this isn't a row-insertion test."""
    from cinis.models.geography import City

    savepoint = sqlalchemy_session.begin_nested()
    try:
        sqlalchemy_session.query(City).update({City.IsPrimaryActive: False})
        sqlalchemy_session.flush()

        repo = CityRepository(sqlalchemy_session)
        with pytest.raises(CityNotFoundError):
            repo.get_primary_active_city()
    finally:
        savepoint.rollback()

    # Confirm the rollback actually restored real state.
    repo = CityRepository(sqlalchemy_session)
    city = repo.get_primary_active_city()
    assert city.Name == "CityScape"
