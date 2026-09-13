"""
Unit tests for NeedsService, using fake repositories rather than a real
database. Real SQL behavior is covered in tests/integration/test_needs.py.
"""

from cinis.services.needs_service import NeedsService


class _FakePopulationRepository:
    def __init__(self, population_by_group: dict[str, int]):
        self._population_by_group = population_by_group

    def get_population_by_city(self, city_id: int) -> dict[str, int]:
        return self._population_by_group


class _FakeNeedsRepository:
    def __init__(self, rates: list[tuple[str, str, float, str]]):
        self._rates = rates

    def get_consumption_rates(self):
        return self._rates


def test_calculate_daily_need_totals_sums_across_group_types():
    population_repo = _FakePopulationRepository({"ADULT": 100, "CHILD": 20})
    needs_repo = _FakeNeedsRepository(
        [
            ("ADULT", "FOOD", 1.0, "KG"),
            ("CHILD", "FOOD", 0.5, "KG"),
        ]
    )
    service = NeedsService(needs_repo, population_repo)

    totals = service.calculate_daily_need_totals(city_id=1)

    assert len(totals) == 1
    food_total = totals[0]
    assert food_total.need_type_code == "FOOD"
    assert food_total.unit_code == "KG"
    # 100 * 1.0 + 20 * 0.5 = 110
    assert food_total.total_quantity == 110.0


def test_calculate_daily_need_totals_handles_multiple_need_types():
    population_repo = _FakePopulationRepository({"ADULT": 100, "CHILD": 20})
    needs_repo = _FakeNeedsRepository(
        [
            ("ADULT", "FOOD", 1.0, "KG"),
            ("CHILD", "FOOD", 0.5, "KG"),
            ("ADULT", "BASIC_GOODS", 0.2, "EA"),
            ("CHILD", "BASIC_GOODS", 0.1, "EA"),
        ]
    )
    service = NeedsService(needs_repo, population_repo)

    totals = {t.need_type_code: t for t in service.calculate_daily_need_totals(city_id=1)}

    assert totals["FOOD"].total_quantity == 110.0
    assert totals["BASIC_GOODS"].total_quantity == 22.0
    assert totals["BASIC_GOODS"].unit_code == "EA"


def test_calculate_daily_need_totals_with_zero_population_gives_zero():
    population_repo = _FakePopulationRepository({"ADULT": 0, "CHILD": 0})
    needs_repo = _FakeNeedsRepository([("ADULT", "FOOD", 1.0, "KG")])
    service = NeedsService(needs_repo, population_repo)

    totals = service.calculate_daily_need_totals(city_id=1)

    assert totals[0].total_quantity == 0.0


def test_calculate_daily_need_totals_missing_group_in_population_defaults_to_zero():
    # Rate exists for a group type with no PopulationGroup row at all.
    population_repo = _FakePopulationRepository({"ADULT": 100})
    needs_repo = _FakeNeedsRepository(
        [("ADULT", "FOOD", 1.0, "KG"), ("CHILD", "FOOD", 0.5, "KG")]
    )
    service = NeedsService(needs_repo, population_repo)

    totals = service.calculate_daily_need_totals(city_id=1)

    assert totals[0].total_quantity == 100.0
