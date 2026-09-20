"""Unit tests for validate_ledger_trace - pure validation, no database."""

import pytest

from cinis.rules.ledger_rules import validate_ledger_trace


def test_neither_id_is_valid():
    validate_ledger_trace(None, None)


def test_both_ids_is_valid():
    validate_ledger_trace(1, 1)
    validate_ledger_trace(42, 1000)


def test_run_without_tick_raises():
    with pytest.raises(ValueError, match="together"):
        validate_ledger_trace(1, None)


def test_tick_without_run_raises():
    with pytest.raises(ValueError, match="together"):
        validate_ledger_trace(None, 5)


@pytest.mark.parametrize("tick", [0, -1])
def test_tick_below_one_raises(tick):
    with pytest.raises(ValueError, match="1 or greater"):
        validate_ledger_trace(1, tick)
