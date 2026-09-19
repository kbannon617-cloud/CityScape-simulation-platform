"""
Market repository. Read-only for this milestone step, matching the
catalog-first pattern used for Production and Vehicles - price lookups
and the city's market, not yet a running buy/sell execution service.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.models.market import Market, MarketResourcePrice


class MarketNotFoundError(RuntimeError):
    """Raised when a city has no Market row - should never happen once
    seed data is applied, but checked explicitly rather than propagating
    a silent None."""


class ResourcePriceNotFoundError(RuntimeError):
    """Raised when a resource has no seeded price for a scenario."""


class MarketRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_market(self, city_id: int) -> Market:
        market = self._session.query(Market).filter(Market.CityID == city_id).one_or_none()
        if market is None:
            raise MarketNotFoundError(f"No Market found for CityID={city_id}")
        return market

    def get_resource_price(self, scenario_id: int, resource_code: str) -> Decimal:
        from cinis.models.inventory import Resource

        price = (
            self._session.query(MarketResourcePrice.UnitPrice)
            .join(Resource, Resource.ResourceID == MarketResourcePrice.ResourceID)
            .filter(
                MarketResourcePrice.ScenarioID == scenario_id,
                Resource.Code == resource_code,
            )
            .one_or_none()
        )
        if price is None:
            raise ResourcePriceNotFoundError(
                f"No MarketResourcePrice found for ScenarioID={scenario_id}, "
                f"Resource Code={resource_code!r}"
            )
        return price[0]
