"""
Need-to-resource mapping repository. Isolates all SQL access for
NeedTypeResource (ADR-0010), per Document 6's layering.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from cinis.models.inventory import Resource
from cinis.models.needs import NeedType, NeedTypeResource


@dataclass(frozen=True)
class MappedResource:
    resource_id: int
    resource_code: str


class NeedResourceRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_resources_by_need_type(self) -> dict[str, list[MappedResource]]:
        """Return, for every need type that has at least one mapping, its
        resources in consumption-priority order (priority 1 first).

        A need type with no mapping is absent from the result (sparse, per
        the seeding convention): "not mapped" means "not modeled yet".
        """
        rows = (
            self._session.query(NeedType.Code, Resource.ResourceID, Resource.Code)
            .select_from(NeedTypeResource)
            .join(NeedType, NeedType.NeedTypeID == NeedTypeResource.NeedTypeID)
            .join(Resource, Resource.ResourceID == NeedTypeResource.ResourceID)
            .order_by(NeedType.Code, NeedTypeResource.ConsumptionPriority)
            .all()
        )

        mapping: dict[str, list[MappedResource]] = {}
        for need_code, resource_id, resource_code in rows:
            mapping.setdefault(need_code, []).append(
                MappedResource(resource_id=resource_id, resource_code=resource_code)
            )
        return mapping
