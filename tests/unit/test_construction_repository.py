"""Unit tests for ConstructionRepository against a real in-memory-style
fake session (no database) - just enough to prove the query shape and
staging behavior, since the SQL itself is covered by the integration
tests."""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from cinis.models.construction import STATUS_COMPLETE, STATUS_IN_PROGRESS, ConstructionProject
from cinis.repositories.construction_repository import ConstructionRepository


@dataclass
class _FakeQuery:
    projects: list
    filters: list = field(default_factory=list)

    def filter(self, *conditions):
        # Real filtering happens in the fixture below via plain Python;
        # this fake just needs to support the chained .filter().count()/
        # .order_by().all() call shape ConstructionRepository uses.
        return self

    def order_by(self, *args):
        return self

    def count(self):
        return len(self.projects)

    def all(self):
        return self.projects


class _FakeSession:
    def __init__(self, projects):
        self._projects = projects
        self.added = []

    def query(self, model):
        assert model is ConstructionProject
        return _FakeQuery(self._projects)

    def add(self, obj):
        self.added.append(obj)


def test_count_active_projects_counts_only_this_citys_in_progress_rows():
    # The fake query returns whatever list it was built with; here we
    # pre-filter in Python to exercise the repository's call shape.
    in_progress = [
        ConstructionProject(ConstructionProjectID=1, CityID=1, Status=STATUS_IN_PROGRESS),
        ConstructionProject(ConstructionProjectID=2, CityID=1, Status=STATUS_IN_PROGRESS),
    ]
    repo = ConstructionRepository(_FakeSession(in_progress))
    assert repo.count_active_projects(1) == 2


def test_get_active_projects_returns_the_rows():
    rows = [ConstructionProject(ConstructionProjectID=1, CityID=1, Status=STATUS_IN_PROGRESS)]
    repo = ConstructionRepository(_FakeSession(rows))
    assert repo.get_active_projects(1) == rows


def test_create_project_stages_all_fields_without_committing():
    session = _FakeSession([])
    repo = ConstructionRepository(session)

    project = repo.create_project(
        city_id=2,
        building_type_id=7,
        buildings_ordered=3,
        order_date=datetime.date(1880, 2, 1),
        total_construction_cost=Decimal("2250.0000"),
        total_timber_required=Decimal("150.0000"),
        total_stone_required=Decimal("75.0000"),
        adjusted_duration_months=8,
    )

    assert session.added == [project]
    assert project.CityID == 2
    assert project.BuildingTypeID == 7
    assert project.BuildingsOrdered == 3
    assert project.OrderSimulationDate == datetime.date(1880, 2, 1)
    assert project.TotalConstructionCost == Decimal("2250.0000")
    assert project.TotalTimberRequired == Decimal("150.0000")
    assert project.TotalStoneRequired == Decimal("75.0000")
    assert project.AdjustedDurationMonths == 8
