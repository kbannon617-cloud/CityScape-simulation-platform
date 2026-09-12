"""Shared SQLAlchemy declarative base for all Cinis ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
