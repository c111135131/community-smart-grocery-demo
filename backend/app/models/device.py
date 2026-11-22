"""IoT device sequence state and event audit."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str] = mapped_column(String(128))
    # Highest accepted sequence number; -1 means "nothing accepted yet".
    last_sequence_number: Mapped[int] = mapped_column(
        Integer, default=-1, server_default="-1"
    )


class IotEvent(Base):
    """Audit record of every frame the gateway received, accepted or rejected.

    Packet-derived columns are nullable because a malformed frame (wrong length,
    wrong header, unknown device ...) cannot always be parsed into these fields.
    """

    __tablename__ = "iot_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int | None] = mapped_column(ForeignKey("residents.id"), nullable=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True, index=True
    )
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    command: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packet_hex: Mapped[str] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(16))  # ACCEPTED | REJECTED
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
