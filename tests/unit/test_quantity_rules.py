"""Unit tests for quantity_rules - pure Decimal helpers, no database."""

from decimal import Decimal

import pytest

from cinis.rules.quantity_rules import LEDGER_PRECISION, floor_to_ledger_precision


def test_value_already_at_four_decimals_is_unchanged():
    assert floor_to_ledger_precision(Decimal("110.0000")) == Decimal("110.0000")


def test_extra_decimals_are_dropped_not_rounded_up():
    assert floor_to_ledger_precision(Decimal("1.99999")) == Decimal("1.9999")
    assert floor_to_ledger_precision(Decimal("0.00019")) == Decimal("0.0001")


def test_half_way_values_go_down_never_up():
    assert floor_to_ledger_precision(Decimal("2.00005")) == Decimal("2.0000")


def test_floor_means_toward_negative_infinity():
    assert floor_to_ledger_precision(Decimal("-0.00001")) == Decimal("-0.0001")


def test_result_always_has_four_decimal_places():
    assert floor_to_ledger_precision(Decimal("88")).as_tuple().exponent == -4
    assert floor_to_ledger_precision(Decimal("88.5")).as_tuple().exponent == -4


def test_integer_input_works():
    assert floor_to_ledger_precision(Decimal(5)) == Decimal("5.0000")


@pytest.mark.parametrize("value", ["0.3", "12.34567", "99.99999"])
def test_is_deterministic(value):
    assert floor_to_ledger_precision(Decimal(value)) == floor_to_ledger_precision(Decimal(value))


def test_ledger_precision_matches_the_decimal_18_4_columns():
    assert LEDGER_PRECISION == Decimal("0.0001")
