"""Unit tests verifying the NeedTypeResource model maps to migration 0021."""

from sqlalchemy import Integer

from cinis.models.needs import NeedTypeResource


def test_uses_int_primary_key():
    column = NeedTypeResource.__table__.columns["NeedTypeResourceID"]
    assert isinstance(column.type, Integer)
    assert column.primary_key


def test_all_mapping_columns_are_required():
    columns = NeedTypeResource.__table__.columns
    for name in ("NeedTypeID", "ResourceID", "ConsumptionPriority"):
        assert not columns[name].nullable


def test_has_foreign_keys_to_need_type_and_resource():
    fk_targets = {fk.target_fullname for fk in NeedTypeResource.__table__.foreign_keys}
    assert fk_targets == {"NeedType.NeedTypeID", "Resource.ResourceID"}


def test_constraints_match_migration():
    names = {c.name for c in NeedTypeResource.__table__.constraints if c.name}
    assert "UQ_NeedTypeResource_NeedType_Resource" in names
    assert "UQ_NeedTypeResource_NeedType_Priority" in names
    assert "CK_NeedTypeResource_ConsumptionPriority_Positive" in names


def test_is_registered_in_models_package():
    import cinis.models as models

    assert models.NeedTypeResource is NeedTypeResource
    assert "NeedTypeResource" in models.__all__


def test_relationships_resolve_against_the_full_mapper_configuration():
    from sqlalchemy.orm import configure_mappers

    import cinis.models  # noqa: F401  (registers every model, including Resource)

    configure_mappers()
