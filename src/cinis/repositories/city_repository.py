"""
City repository. All SQL/ORM access for City is isolated here, per the
layered architecture in Document 6: services and future simulation code
depend on repository methods like get_primary_active_city, never on
SQLAlchemy sessions or raw SQL directly.

This is the first repository in the codebase and is meant as a template:
Milestone 2's population repository (and later repositories) should follow
the same shape - a thin class wrapping a Session, one method per real,
named query need, no generic/speculative CRUD surface.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.geography import City


class CityNotFoundError(RuntimeError):
    """Raised when no primary active city exists, which should never
    happen once Milestone 1's seed data (0003) has been applied and the
    0004 constraint is in place, but is still checked explicitly rather
    than allowing a None to propagate silently."""


class CityRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_primary_active_city(self) -> City:
        """Return the single primary active city (Document 4 MVP scope).

        The 0004 migration's filtered unique index guarantees at most one
        such row exists at the database level; this method still checks
        for zero rows explicitly, since the database cannot guarantee at
        least one (e.g. seed data not yet applied).
        """
        city = (
            self._session.query(City)
            .filter(City.IsPrimaryActive == True)  # noqa: E712
            .one_or_none()
        )
        if city is None:
            raise CityNotFoundError(
                "No primary active city found. Has migration 0003 "
                "(seed data) been applied?"
            )
        return city
