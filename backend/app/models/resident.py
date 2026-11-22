"""Resident and health profile models (see docs/DATABASE.md)."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonType


class Resident(Base):
    __tablename__ = "residents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Demo card identifier. Not a real credential: see resident_service.login.
    card_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    health_profile: Mapped["HealthProfile"] = relationship(
        back_populates="resident", uselist=False, cascade="all, delete-orphan"
    )


class HealthProfile(Base):
    __tablename__ = "health_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(
        ForeignKey("residents.id", ondelete="CASCADE"), unique=True
    )
    dietary_preferences: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    allergies: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    resident: Mapped[Resident] = relationship(back_populates="health_profile")
