"""Declarative base and shared column types."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# JSONB on PostgreSQL (default DB); plain JSON elsewhere (e.g. SQLite in unit tests).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Base class for all ORM models."""
