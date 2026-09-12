"""Reference data models mapping to Document 5's Currency and UnitOfMeasure tables."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cinis.models.base import Base


class Currency(Base):
    __tablename__ = "Currency"

    CurrencyID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    Symbol: Mapped[str | None] = mapped_column(String(5), nullable=True)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"Currency(CurrencyID={self.CurrencyID!r}, Code={self.Code!r})"


class UnitOfMeasure(Base):
    __tablename__ = "UnitOfMeasure"

    UnitOfMeasureID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    Name: Mapped[str] = mapped_column(String(100), nullable=False)
    CreatedDateTime: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.sysutcdatetime()
    )

    def __repr__(self) -> str:
        return f"UnitOfMeasure(UnitOfMeasureID={self.UnitOfMeasureID!r}, Code={self.Code!r})"
