"""Unit tests verifying the ledger models carry the 0020 run/tick columns."""

import pytest
from sqlalchemy import BigInteger, Integer

from cinis.models.economy import TreasuryLedgerEntry
from cinis.models.inventory import InventoryLedgerEntry

LEDGER_MODELS = [TreasuryLedgerEntry, InventoryLedgerEntry]


@pytest.mark.parametrize("model", LEDGER_MODELS)
def test_run_and_tick_columns_are_nullable_with_expected_types(model):
    columns = model.__table__.columns
    assert isinstance(columns["SimulationRunID"].type, Integer)
    assert isinstance(columns["SimulationTickID"].type, BigInteger)
    assert columns["SimulationRunID"].nullable
    assert columns["SimulationTickID"].nullable


@pytest.mark.parametrize("model", LEDGER_MODELS)
def test_run_column_has_foreign_key_to_simulation_run(model):
    fk_targets = {fk.target_fullname for fk in model.__table__.foreign_keys}
    assert "SimulationRun.SimulationRunID" in fk_targets


@pytest.mark.parametrize("model", LEDGER_MODELS)
def test_check_constraints_match_migration(model):
    names = {c.name for c in model.__table__.constraints if c.name}
    table = model.__tablename__
    assert f"CK_{table}_Trace_BothOrNeither" in names
    assert f"CK_{table}_SimulationTickID_Positive" in names


@pytest.mark.parametrize("model", LEDGER_MODELS)
def test_existing_columns_are_unchanged(model):
    columns = model.__table__.columns
    assert not columns["EntryDate"].nullable
    assert not columns["Amount"].nullable
