"""Unit tests verifying the economy ORM models map to the physical schema."""

from cinis.models.economy import Treasury, TreasuryCategoryType, TreasuryLedgerEntry


def test_treasury_category_type_maps_to_expected_table():
    assert TreasuryCategoryType.__tablename__ == "TreasuryCategoryType"
    columns = {c.name for c in TreasuryCategoryType.__table__.columns}
    assert columns == {"TreasuryCategoryTypeID", "Code", "Name", "CreatedDateTime"}


def test_treasury_has_foreign_keys_to_city_and_currency():
    fk_targets = {fk.target_fullname for fk in Treasury.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert "Currency.CurrencyID" in fk_targets


def test_treasury_cityid_column_is_unique():
    column = Treasury.__table__.columns["CityID"]
    assert column.unique is True


def test_treasury_balance_is_numeric():
    from sqlalchemy import Numeric

    column = Treasury.__table__.columns["Balance"]
    assert isinstance(column.type, Numeric)


def test_treasury_ledger_entry_id_is_bigint():
    from sqlalchemy import BigInteger

    column = TreasuryLedgerEntry.__table__.columns["TreasuryLedgerEntryID"]
    assert isinstance(column.type, BigInteger)


def test_treasury_ledger_entry_has_expected_foreign_keys():
    fk_targets = {fk.target_fullname for fk in TreasuryLedgerEntry.__table__.foreign_keys}
    assert "Treasury.TreasuryID" in fk_targets
    assert "TreasuryCategoryType.TreasuryCategoryTypeID" in fk_targets
