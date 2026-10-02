"""
Unit test for ProductionRepository.get_or_create_building (added in Step
4.5c for ConstructionService.advance_projects) against a fake session -
just the query/create shape, since the SQL itself is covered by the
integration tests. The rest of ProductionRepository is exercised via the
integration suite (tests/integration/test_production*.py), not unit
fakes, so this file covers only the one method Step 4.5c added.
"""

from dataclasses import dataclass, field

from cinis.models.production import Building
from cinis.repositories.production_repository import ProductionRepository


@dataclass
class _FakeQuery:
    result: Building | None

    def filter(self, *conditions):
        return self

    def one_or_none(self):
        return self.result


@dataclass
class _FakeSession:
    existing: Building | None = None
    added: list = field(default_factory=list)
    flushed: bool = False

    def query(self, model):
        assert model is Building
        return _FakeQuery(self.existing)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed = True


def test_returns_the_existing_row_without_creating_anything():
    existing = Building(CityID=1, BuildingTypeID=2, Count=3)
    session = _FakeSession(existing=existing)
    repo = ProductionRepository(session)

    result = repo.get_or_create_building(1, 2)

    assert result is existing
    assert session.added == []
    assert session.flushed is False


def test_creates_a_zero_count_row_when_none_exists_and_flushes():
    session = _FakeSession(existing=None)
    repo = ProductionRepository(session)

    result = repo.get_or_create_building(1, 2)

    assert session.added == [result]
    assert result.CityID == 1
    assert result.BuildingTypeID == 2
    assert result.Count == 0
    assert session.flushed is True
