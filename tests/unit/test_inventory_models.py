"""Unit tests verifying the CityInventory/InventoryLedgerEntry models map to the physical schema."""

from cinis.models.inventory import CityInventory, InventoryLedgerEntry


def test_city_inventory_has_foreign_keys_to_city_and_resource():
    fk_targets = {fk.target_fullname for fk in CityInventory.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert "Resource.ResourceID" in fk_targets


def test_inventory_ledger_entry_has_foreign_key_to_city_inventory():
    fk_targets = {fk.target_fullname for fk in InventoryLedgerEntry.__table__.foreign_keys}
    assert "CityInventory.CityInventoryID" in fk_targets


def test_inventory_ledger_entry_uses_bigint_primary_key():
    from sqlalchemy import BigInteger

    column = InventoryLedgerEntry.__table__.columns["InventoryLedgerEntryID"]
    assert isinstance(column.type, BigInteger)
