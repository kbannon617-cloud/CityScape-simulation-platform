"""
Needs repository. Isolates all SQL access for NeedType/NeedConsumptionRate,
per Document 6's layering.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cinis.models.needs import NeedConsumptionRate, NeedType
from cinis.models.population import PopulationGroupType
from cinis.models.reference import UnitOfMeasure


class NeedsRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all_need_types(self) -> list[str]:
        """Return every seeded need type's Code."""
        rows = self._session.query(NeedType.Code).all()
        return [code for (code,) in rows]

    def get_consumption_rates(self) -> list[tuple[str, str, float, str]]:
        """Return (group_type_code, need_type_code, quantity_per_person_per_day, unit_code)
        for every seeded consumption rate."""
        rows = (
            self._session.query(
                PopulationGroupType.Code,
                NeedType.Code,
                NeedConsumptionRate.QuantityPerPersonPerDay,
                UnitOfMeasure.Code,
            )
            .select_from(NeedConsumptionRate)
            .join(
                PopulationGroupType,
                PopulationGroupType.PopulationGroupTypeID
                == NeedConsumptionRate.PopulationGroupTypeID,
            )
            .join(NeedType, NeedType.NeedTypeID == NeedConsumptionRate.NeedTypeID)
            .join(
                UnitOfMeasure,
                UnitOfMeasure.UnitOfMeasureID == NeedConsumptionRate.UnitOfMeasureID,
            )
            .all()
        )
        return [
            (group_code, need_code, float(qty), unit_code)
            for group_code, need_code, qty, unit_code in rows
        ]
