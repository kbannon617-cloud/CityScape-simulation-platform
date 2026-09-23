"""Unit tests verifying the ConstructionProject model maps to migration 0023."""

import datetime
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric

from cinis.models.construction import (
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    ConstructionProject,
)


def test_uses_int_primary_key():
    column = ConstructionProject.__table__.columns["ConstructionProjectID"]
    assert isinstance(column.type, Integer)
    assert column.primary_key


def test_snapshot_columns_have_the_expected_types():
    columns = ConstructionProject.__table__.columns
    assert isinstance(columns["TotalConstructionCost"].type, Numeric)
    assert isinstance(columns["TotalTimberRequired"].type, Numeric)
    assert isinstance(columns["TotalStoneRequired"].type, Numeric)
    assert isinstance(columns["OrderSimulationDate"].type, Date)


def test_has_foreign_keys_to_city_and_building_type():
    fk_targets = {fk.target_fullname for fk in ConstructionProject.__table__.foreign_keys}
    assert fk_targets == {"City.CityID", "BuildingType.BuildingTypeID"}


def test_months_elapsed_and_status_default_appropriately():
    columns = ConstructionProject.__table__.columns
    assert columns["MonthsElapsed"].default.arg == 0
    assert columns["Status"].default.arg == STATUS_IN_PROGRESS


def test_status_constants_match_the_migration_check_constraint():
    assert STATUS_IN_PROGRESS == "InProgress"
    assert STATUS_COMPLETE == "Complete"


def test_completed_simulation_date_is_nullable():
    assert ConstructionProject.__table__.columns["CompletedSimulationDate"].nullable


def test_check_constraints_match_migration():
    names = {c.name for c in ConstructionProject.__table__.constraints if c.name}
    assert names == {
        "CK_ConstructionProject_BuildingsOrdered_Positive",
        "CK_ConstructionProject_AdjustedDurationMonths_Positive",
        "CK_ConstructionProject_MonthsElapsed_NonNegative",
        "CK_ConstructionProject_Status",
        "CK_ConstructionProject_Completed_Consistency",
    }


def test_is_registered_in_models_package():
    import cinis.models as models

    assert models.ConstructionProject is ConstructionProject
    assert "ConstructionProject" in models.__all__


def test_relationships_resolve_against_the_full_mapper_configuration():
    from sqlalchemy.orm import configure_mappers

    import cinis.models  # noqa: F401

    configure_mappers()


def test_repr_reports_progress():
    project = ConstructionProject(
        ConstructionProjectID=1,
        CityID=1,
        Status=STATUS_IN_PROGRESS,
        MonthsElapsed=2,
        AdjustedDurationMonths=5,
    )
    assert "2" in repr(project) and "5" in repr(project)
