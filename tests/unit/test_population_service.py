"""
Unit tests for PopulationService's orchestration logic, using a minimal
fake repository rather than a real database. This tests that the service
wires the repository and rules together correctly - the rules' own math is
covered separately in test_population_rules.py, and the repository's real
SQL behavior is covered in tests/integration/test_population_aging.py.
"""

from dataclasses import dataclass

import pytest

from cinis.services.population_service import PopulationService


@dataclass
class _FakeGroup:
    Count: int


class _FakeRepository:
    """Implements just enough of PopulationRepository's interface for
    PopulationService to run against, with in-memory state instead of a
    database."""

    def __init__(
        self,
        child_count: int,
        adult_count: int,
        rate_percent: float,
        labor_participation_rate_percent: float = 100.0,
    ):
        self.groups = {"CHILD": _FakeGroup(child_count), "ADULT": _FakeGroup(adult_count)}
        self.rate_percent = rate_percent
        self.labor_participation_rate_percent = labor_participation_rate_percent

    def get_group(self, city_id: int, group_type_code: str):
        return self.groups[group_type_code]

    def get_scenario_parameter(self, scenario_id: int, key: str) -> float:
        if key == "ChildToAdultMonthlyAgingRatePercent":
            return self.rate_percent
        if key == "AdultLaborParticipationRatePercent":
            return self.labor_participation_rate_percent
        raise KeyError(key)


def test_apply_monthly_aging_moves_people_from_child_to_adult():
    repo = _FakeRepository(child_count=1000, adult_count=100, rate_percent=1.5)
    service = PopulationService(repo)

    result = service.apply_monthly_aging(city_id=1, scenario_id=1)

    assert result.aged_count == 15
    assert result.new_child_count == 985
    assert result.new_adult_count == 115


def test_apply_monthly_aging_mutates_the_same_group_objects():
    repo = _FakeRepository(child_count=1000, adult_count=100, rate_percent=1.5)
    service = PopulationService(repo)

    service.apply_monthly_aging(city_id=1, scenario_id=1)

    assert repo.groups["CHILD"].Count == 985
    assert repo.groups["ADULT"].Count == 115


def test_apply_monthly_aging_with_zero_result_does_not_mutate_counts():
    repo = _FakeRepository(child_count=20, adult_count=100, rate_percent=1.5)
    service = PopulationService(repo)

    result = service.apply_monthly_aging(city_id=1, scenario_id=1)

    assert result.aged_count == 0
    assert repo.groups["CHILD"].Count == 20
    assert repo.groups["ADULT"].Count == 100


def test_apply_monthly_aging_propagates_missing_parameter_error():
    class _RepoWithNoParameter(_FakeRepository):
        def get_scenario_parameter(self, city_id, key):
            raise RuntimeError("no parameter configured")

    repo = _RepoWithNoParameter(child_count=100, adult_count=100, rate_percent=0)
    service = PopulationService(repo)

    with pytest.raises(RuntimeError):
        service.apply_monthly_aging(city_id=1, scenario_id=1)


def test_calculate_available_labor_full_participation():
    repo = _FakeRepository(
        child_count=20, adult_count=100, rate_percent=1.5, labor_participation_rate_percent=100
    )
    service = PopulationService(repo)

    assert service.calculate_available_labor(city_id=1, scenario_id=1) == 100


def test_calculate_available_labor_partial_participation_rounds_down():
    repo = _FakeRepository(
        child_count=20, adult_count=101, rate_percent=1.5, labor_participation_rate_percent=90
    )
    service = PopulationService(repo)

    # 101 * 90% = 90.9 -> floors to 90
    assert service.calculate_available_labor(city_id=1, scenario_id=1) == 90


def test_calculate_available_labor_does_not_mutate_population_counts():
    repo = _FakeRepository(child_count=20, adult_count=100, rate_percent=1.5)
    service = PopulationService(repo)

    service.calculate_available_labor(city_id=1, scenario_id=1)

    assert repo.groups["ADULT"].Count == 100
    assert repo.groups["CHILD"].Count == 20
