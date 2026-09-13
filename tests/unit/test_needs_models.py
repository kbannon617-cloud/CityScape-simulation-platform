"""Unit tests verifying the needs ORM models map to the physical schema."""

from cinis.models.needs import NeedConsumptionRate, NeedType


def test_need_type_maps_to_expected_table():
    assert NeedType.__tablename__ == "NeedType"
    columns = {c.name for c in NeedType.__table__.columns}
    assert columns == {"NeedTypeID", "Code", "Name", "CreatedDateTime"}


def test_need_consumption_rate_has_expected_foreign_keys():
    fk_targets = {fk.target_fullname for fk in NeedConsumptionRate.__table__.foreign_keys}
    assert "PopulationGroupType.PopulationGroupTypeID" in fk_targets
    assert "NeedType.NeedTypeID" in fk_targets
    assert "UnitOfMeasure.UnitOfMeasureID" in fk_targets


def test_need_consumption_rate_quantity_is_numeric():
    from sqlalchemy import Numeric

    column = NeedConsumptionRate.__table__.columns["QuantityPerPersonPerDay"]
    assert isinstance(column.type, Numeric)
