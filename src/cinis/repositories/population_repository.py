"""
Population repository. Follows the same shape as CityRepository: a thin
class wrapping a Session, one method per real named query need.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.population import PopulationGroup, PopulationGroupType, ScenarioParameter


class ScenarioParameterNotFoundError(RuntimeError):
    """Raised when a requested scenario parameter has not been seeded."""


class PopulationGroupNotFoundError(RuntimeError):
    """Raised when a requested (city, group type) population group does
    not exist. This should never happen once Milestone 1/2 seed data has
    been applied, but is checked explicitly rather than propagating a
    silent None."""


class PopulationRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_group(self, city_id: int, group_type_code: str) -> PopulationGroup:
        """Return the live PopulationGroup ORM object for a city/group type.

        Unlike get_population_by_city (which returns plain counts for
        reporting), this returns the mapped object itself so callers -
        specifically PopulationService - can mutate .Count and rely on
        the same Session to persist the change.
        """
        group = (
            self._session.query(PopulationGroup)
            .join(
                PopulationGroupType,
                PopulationGroupType.PopulationGroupTypeID
                == PopulationGroup.PopulationGroupTypeID,
            )
            .filter(
                PopulationGroup.CityID == city_id,
                PopulationGroupType.Code == group_type_code,
            )
            .one_or_none()
        )
        if group is None:
            raise PopulationGroupNotFoundError(
                f"No PopulationGroup found for CityID={city_id}, "
                f"group type {group_type_code!r}"
            )
        return group

    def get_population_by_city(self, city_id: int) -> dict[str, int]:
        """Return {group_type_code: count} for every population group in a city."""
        rows = (
            self._session.query(PopulationGroupType.Code, PopulationGroup.Count)
            .join(
                PopulationGroup,
                PopulationGroup.PopulationGroupTypeID
                == PopulationGroupType.PopulationGroupTypeID,
            )
            .filter(PopulationGroup.CityID == city_id)
            .all()
        )
        return {code: count for code, count in rows}

    def get_total_population(self, city_id: int) -> int:
        """Return the sum of all group counts for a city (0 if none exist)."""
        counts = self.get_population_by_city(city_id)
        return sum(counts.values())

    def get_scenario_parameter(self, scenario_id: int, key: str) -> float:
        """Return a scenario's configured parameter value as a float.

        Raises ScenarioParameterNotFoundError rather than returning a
        silent default, since a missing rate (e.g. an aging rate) should
        be a visible setup problem, not quietly treated as zero.
        """
        param = (
            self._session.query(ScenarioParameter)
            .filter(
                ScenarioParameter.ScenarioID == scenario_id,
                ScenarioParameter.ParameterKey == key,
            )
            .one_or_none()
        )
        if param is None:
            raise ScenarioParameterNotFoundError(
                f"No ScenarioParameter {key!r} found for ScenarioID={scenario_id}"
            )
        return float(param.ParameterValue)
