"""
Market repository. Price lookups, the city's market, and
record_transaction (Step 4.6a) - the one write path this repository
supports, used by MarketService.buy/sell to log each trade.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from cinis.models.market import Market, MarketResourcePrice, MarketTransaction


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

    def record_transaction(
        self,
        market_id: int,
        resource_id: int,
        transaction_type: str,
        quantity: Decimal,
        unit_price: Decimal,
        total_value: Decimal,
        transaction_date: datetime.date,
    ) -> MarketTransaction:
        """Create and stage a MarketTransaction row. Does not commit; the
        caller (MarketService) owns the transaction boundary."""
        transaction = MarketTransaction(
            MarketID=market_id,
            ResourceID=resource_id,
            TransactionType=transaction_type,
            Quantity=quantity,
            UnitPrice=unit_price,
            TotalValue=total_value,
            TransactionDate=transaction_date,
        )
        self._session.add(transaction)
        return transaction
