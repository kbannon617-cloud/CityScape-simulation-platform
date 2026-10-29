"""
M5 Step 5.3: tests for slice_oracle.py. No database - these run everywhere.

The oracle is the yardstick the live slice test measures the real engine
against, so it must itself be right. The first test is a known-answer test
using the real seeded catalog numbers (migrations 0008, 0012, 0022), checked
against a hand calculation written out in the comments. The rest pin each
rule's edge cases with tiny synthetic catalogs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from slice_oracle import (
    BuildingSpec,
    Catalog,
    DayStart,
    ModelError,
    Order,
    Trade,
    expected_day,
)

D = Decimal

# --- The real seeded catalog (placeholder rates, unbalanced by design) -----

SEEDED_CATALOG = Catalog(
    buildings={
        "B-002": BuildingSpec(workers=5, outputs={"R-001": D("100")}),                       # Wheat Farm
        "B-009": BuildingSpec(workers=25, inputs={"R-004": D("100")}, outputs={"R-005": D("50")}),  # Saw Mill
        "B-007": BuildingSpec(workers=0, timber=D("50"), stone=D("50")),                     # Construction Crew
    },
    need_rates={
        "FOOD": {"ADULT": D("1.0"), "CHILD": D("0.5")},
        "HEATING": {"ADULT": D("0.8"), "CHILD": D("0.4")},
        "BASIC_GOODS": {"ADULT": D("0.2"), "CHILD": D("0.1")},   # unmapped: skipped
    },
    need_resources={
        "FOOD": ("R-001", "R-002", "R-009", "R-010"),
        "HEATING": ("R-004",),
    },
    prices={"R-001": D("2.0000"), "R-005": D("3.0000")},
)

SLICE_START = DayStart(
    adults=100,
    children=200,
    buildings={"B-002": 2, "B-009": 1},
    stock={"R-001": D("1000"), "R-004": D("1000"), "R-003": D("1000")},
    treasury=D("1000.00"),
    aging_rate_percent=D("1.5"),
    participation_percent=D("100"),
    monthly_construction_budget=D("100"),
    bonus_per_crew=D("0.0005"),
)


def test_known_answer_for_the_default_slice_day():
    day = expected_day(
        SEEDED_CATALOG,
        SLICE_START,
        orders=(Order("B-007", 1),),
        trades=(Trade("sell", "R-005", D("50")), Trade("buy", "R-001", D("100"))),
    )

    # Aging: floor(200 x 1.5%) = 3 children become adults.
    assert (day.aged, day.adults, day.children) == (3, 103, 197)

    # Production: labor = floor(103 x 100%) = 103.
    #   B-002 first (code order): min(2, 103 // 5 = 20) = 2 staffed, 10 workers -> +200 Wheat.
    #   B-009 next: min(1, 93 // 25 = 3) = 1 staffed, 25 workers; Timber 950 >= 100,
    #   so -100 Timber and +50 Lumber.
    assert day.production["B-002"].staffed == 2
    assert day.production["B-002"].outputs == {"R-001": D("200")}
    assert day.production["B-009"].staffed == 1
    assert day.production["B-009"].inputs == {"R-004": D("100")}
    assert day.production["B-009"].outputs == {"R-005": D("50")}

    # Construction: the Crew costs nothing, so base duration is 1 month and one
    # month-boundary advance completes it the same tick.
    assert day.completed == [("B-007", 1)]
    assert day.in_progress == []
    assert day.buildings == {"B-002": 2, "B-009": 1, "B-007": 1}

    # Needs, from post-aging headcounts (103 adults, 197 children):
    #   FOOD    = 103 x 1.0 + 197 x 0.5 = 201.5  (Wheat)
    #   HEATING = 103 x 0.8 + 197 x 0.4 = 161.2  (Timber)
    #   BASIC_GOODS has no resource mapping: skipped entirely.
    assert [(n.need_code, n.needed, n.consumed) for n in day.needs] == [
        ("FOOD", D("201.5000"), D("201.5000")),
        ("HEATING", D("161.2000"), D("161.2000")),
    ]
    assert day.shortfalls == []

    # Trades at fixed prices: sell 50 Lumber @3 = +150; buy 100 Wheat @2 = -200.
    assert [(t.side, t.resource_code, t.quantity, t.unit_price, t.total_value) for t in day.transactions] == [
        ("sell", "R-005", D("50"), D("3.0000"), D("150.0000")),
        ("buy", "R-001", D("100"), D("2.0000"), D("200.0000")),
    ]

    # End-of-day stock:
    #   Wheat  1000 + 200 produced - 201.5 eaten + 100 bought = 1098.5
    #   Timber 1000 - 50 (Crew) - 100 (Saw Mill) - 161.2 (heating) = 688.8
    #   Stone  1000 - 50 (Crew) = 950
    #   Lumber 0 + 50 produced - 50 sold = 0
    assert day.stock["R-001"] == D("1098.5")
    assert day.stock["R-004"] == D("688.8")
    assert day.stock["R-003"] == D("950")
    assert day.stock["R-005"] == D("0")

    # Treasury: 1000 + 150 - 200 = 950 (the Crew costs 0, so no construction entry).
    assert day.treasury == D("950.00")


def test_a_day_with_no_script_still_ages_produces_and_consumes():
    day = expected_day(SEEDED_CATALOG, SLICE_START)

    assert day.aged == 3
    assert day.transactions == []
    assert day.completed == []
    assert day.treasury == D("1000.00")
    assert day.stock["R-005"] == D("50")      # Lumber is produced and simply kept


# --- Labor allocation --------------------------------------------------------


def test_labor_is_first_come_first_served_by_building_code():
    # 10 adults, no children: labor 10. B-002 (5 workers) staffs both farms and
    # uses all 10, so B-009 (25 workers, later code) gets nobody.
    start = DayStart(
        adults=10, children=0, buildings={"B-002": 2, "B-009": 1},
        stock={"R-004": D("500")}, treasury=D("0"),
        aging_rate_percent=D("1.5"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0.0005"),
    )
    day = expected_day(SEEDED_CATALOG, start)

    assert day.production["B-002"].staffed == 2
    assert day.production["B-009"].skipped_reason == "No labor available"
    assert "R-005" not in day.stock


def test_participation_rate_limits_the_labor_pool():
    start = DayStart(
        adults=100, children=0, buildings={"B-009": 1},
        stock={"R-004": D("500")}, treasury=D("0"),
        aging_rate_percent=D("1.5"), participation_percent=D("20"),   # 20 workers < 25 needed
        monthly_construction_budget=D("100"), bonus_per_crew=D("0.0005"),
    )
    day = expected_day(SEEDED_CATALOG, start)

    assert day.production["B-009"].skipped_reason == "No labor available"


def test_missing_inputs_idle_the_building_but_the_labor_is_still_spent():
    # Saw Mill staffed (25 of 30 labor) but only 40 Timber on hand (needs 100):
    # nothing produced, and the 25 workers are gone before the farm is considered.
    catalog = Catalog(
        buildings={
            "B-001": BuildingSpec(workers=25, inputs={"R-004": D("100")}, outputs={"R-005": D("50")}),
            "B-002": BuildingSpec(workers=5, outputs={"R-001": D("100")}),
        },
        need_rates={}, need_resources={}, prices={},
    )
    start = DayStart(
        adults=30, children=0, buildings={"B-001": 1, "B-002": 2},
        stock={"R-004": D("40")}, treasury=D("0"),
        aging_rate_percent=D("0"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0"),
    )
    day = expected_day(catalog, start)

    assert day.production["B-001"].skipped_reason == "Insufficient input inventory"
    assert day.production["B-001"].workers_used == 25
    assert day.stock["R-004"] == D("40")                  # nothing consumed
    assert day.production["B-002"].staffed == 1           # only 5 workers left: one farm
    assert day.stock["R-001"] == D("100")


# --- Aging -------------------------------------------------------------------


def test_aging_floors_and_drops_the_remainder():
    # floor(3 x 1.5%) = 0: nobody ages (the known small-population effect).
    start = DayStart(
        adults=10, children=3, buildings={}, stock={}, treasury=D("0"),
        aging_rate_percent=D("1.5"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0"),
    )
    assert expected_day(SEEDED_CATALOG, start).aged == 0


# --- Needs -------------------------------------------------------------------


def _needs_start(wheat: str, trout: str = "0") -> DayStart:
    return DayStart(
        adults=10, children=0, buildings={},
        stock={"R-001": D(wheat), "R-002": D(trout)}, treasury=D("0"),
        aging_rate_percent=D("0"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0"),
    )


FOOD_ONLY = Catalog(
    buildings={}, need_rates={"FOOD": {"ADULT": D("1.0")}},
    need_resources={"FOOD": ("R-001", "R-002")}, prices={},
)


def test_a_need_falls_through_to_the_next_priority_resource():
    # 10 food needed; only 4 Wheat, so 6 comes from Trout.
    day = expected_day(FOOD_ONLY, _needs_start(wheat="4", trout="20"))

    assert day.stock["R-001"] == D("0")
    assert day.stock["R-002"] == D("14")
    assert day.shortfalls == []


def test_an_unmet_need_is_a_shortfall_not_an_error():
    day = expected_day(FOOD_ONLY, _needs_start(wheat="4", trout="3"))

    assert day.stock["R-001"] == D("0") and day.stock["R-002"] == D("0")
    [shortfall] = day.shortfalls
    assert (shortfall.need_code, shortfall.needed, shortfall.consumed, shortfall.shortfall) == (
        "FOOD", D("10.0000"), D("7.0000"), D("3.0000"),
    )


def test_a_need_is_floored_to_four_decimals():
    # 7 adults x 0.33335 = 2.33345. Floor gives 2.3334; round-half-up would give
    # 2.3335. The fifth decimal is deliberately a 5 so the two cannot agree.
    catalog = Catalog(
        buildings={}, need_rates={"FOOD": {"ADULT": D("0.33335")}},
        need_resources={"FOOD": ("R-001",)}, prices={},
    )
    start = DayStart(
        adults=7, children=0, buildings={}, stock={"R-001": D("10")}, treasury=D("0"),
        aging_rate_percent=D("0"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0"),
    )
    day = expected_day(catalog, start)

    assert day.needs[0].needed == D("2.3334")
    assert day.stock["R-001"] == D("7.6666")


# --- Construction ------------------------------------------------------------


def test_a_costly_order_takes_several_months_and_stays_in_progress():
    # Cost 500 against a monthly budget of 100: ceil(500 / 100) = 5 months.
    catalog = Catalog(
        buildings={"B-005": BuildingSpec(workers=0, construction_cost=D("500"), timber=D("10"), stone=D("10"))},
        need_rates={}, need_resources={}, prices={},
    )
    start = DayStart(
        adults=0, children=0, buildings={}, stock={"R-004": D("100"), "R-003": D("100")},
        treasury=D("800"), aging_rate_percent=D("0"), participation_percent=D("100"),
        monthly_construction_budget=D("100"), bonus_per_crew=D("0.0005"),
    )
    day = expected_day(catalog, start, orders=(Order("B-005", 1),))

    assert day.completed == []
    assert day.in_progress == [("B-005", 1, 5, 1)]
    assert day.buildings == {}
    assert day.treasury == D("300")
    assert day.stock["R-004"] == D("90") and day.stock["R-003"] == D("90")


def test_completed_crews_shorten_a_later_order_but_never_below_one_month():
    # 2 completed crews x 0.0005 = 0.001 bonus: 5 / 1.001 = 4.995 -> ceil 5 (no change yet).
    # 4000 crews x 0.0005 = 2.0 bonus: 5 / 3 = 1.67 -> ceil 2.
    catalog = Catalog(
        buildings={"B-005": BuildingSpec(workers=0, construction_cost=D("500"))},
        need_rates={}, need_resources={}, prices={},
    )

    def duration_with(crews: int) -> int:
        start = DayStart(
            adults=0, children=0, buildings={"B-007": crews}, stock={}, treasury=D("800"),
            aging_rate_percent=D("0"), participation_percent=D("100"),
            monthly_construction_budget=D("100"), bonus_per_crew=D("0.0005"),
        )
        return expected_day(
            Catalog(buildings={**catalog.buildings, "B-007": BuildingSpec(workers=0)},
                    need_rates={}, need_resources={}, prices={}),
            start, orders=(Order("B-005", 1),),
        ).in_progress[0][2]

    assert duration_with(2) == 5
    assert duration_with(4000) == 2


# --- Trades and the happy-path guard -----------------------------------------


def test_selling_more_than_the_stock_is_not_a_happy_path_day():
    with pytest.raises(ModelError, match="stock would go negative"):
        expected_day(SEEDED_CATALOG, SLICE_START, trades=(Trade("sell", "R-005", D("51")),))   # only 50 made


def test_buying_more_than_the_treasury_can_pay_is_not_a_happy_path_day():
    with pytest.raises(ModelError, match="treasury would go negative"):
        expected_day(SEEDED_CATALOG, SLICE_START, trades=(Trade("buy", "R-001", D("501")),))   # 501 x 2 > 1000


def test_a_trade_side_must_be_sell_or_buy():
    with pytest.raises(ValueError, match="side must be"):
        Trade("barter", "R-001", D("1"))
