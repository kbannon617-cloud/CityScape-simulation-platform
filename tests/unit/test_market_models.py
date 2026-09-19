"""Unit tests verifying the market ORM models map to the physical schema."""

from cinis.models.market import Market, MarketResourcePrice, MarketTransaction


def test_market_unique_to_city():
    fk_targets = {fk.target_fullname for fk in Market.__table__.foreign_keys}
    assert "City.CityID" in fk_targets
    assert Market.__table__.columns["CityID"].unique is True


def test_market_resource_price_has_expected_foreign_keys():
    fk_targets = {fk.target_fullname for fk in MarketResourcePrice.__table__.foreign_keys}
    assert "Scenario.ScenarioID" in fk_targets
    assert "Resource.ResourceID" in fk_targets
    assert "Currency.CurrencyID" in fk_targets


def test_market_transaction_uses_bigint_primary_key():
    from sqlalchemy import BigInteger

    column = MarketTransaction.__table__.columns["MarketTransactionID"]
    assert isinstance(column.type, BigInteger)


def test_market_transaction_has_foreign_keys_to_market_and_resource():
    fk_targets = {fk.target_fullname for fk in MarketTransaction.__table__.foreign_keys}
    assert "Market.MarketID" in fk_targets
    assert "Resource.ResourceID" in fk_targets
