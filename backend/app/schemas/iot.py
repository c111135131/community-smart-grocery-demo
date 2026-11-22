"""Schemas for IoT event simulation, gateway results and audit views."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.cart import CartOut

CommandName = Literal["BIND_CARD", "ADD_ITEM", "REMOVE_ITEM", "CHECKOUT", "ALERT"]

_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
_MAX_RAW_BYTES = 128  # sanity cap; real frames are 16 bytes


class CartEventRequest(BaseModel):
    """Simulated device event. The backend encodes it into the 16-byte packet."""

    device_id: int = Field(ge=0, le=0xFFFF, examples=[1])
    command: CommandName = Field(examples=["ADD_ITEM"])
    product_code: int = Field(ge=0, le=0xFFFF, examples=[101])
    weight_grams: int = Field(ge=0, le=0xFFFFFF, examples=[320])


class RawPacketRequest(BaseModel):
    """Raw frame as hex, to demo replayed / tampered / malformed packets."""

    packet_hex: str = Field(examples=["AA550001000102006500014000D9847C"])

    @field_validator("packet_hex")
    @classmethod
    def normalize_hex(cls, v: str) -> str:
        cleaned = re.sub(r"\s+", "", v)
        if cleaned.lower().startswith("0x"):
            cleaned = cleaned[2:]
        if not cleaned or not _HEX_RE.match(cleaned):
            raise ValueError("packet_hex must contain only hexadecimal characters")
        if len(cleaned) % 2 != 0:
            raise ValueError("packet_hex must have an even number of hex digits")
        if len(cleaned) > _MAX_RAW_BYTES * 2:
            raise ValueError(f"packet_hex is limited to {_MAX_RAW_BYTES} bytes")
        return cleaned.upper()


class ParsedPacketOut(BaseModel):
    device_id: int
    sequence_number: int
    command: str
    product_code: int
    weight_grams: int
    flags: int


class ValidationOut(BaseModel):
    """Result of each check, in validation order. null = step not reached."""

    length_valid: bool | None
    header_valid: bool | None
    command_valid: bool | None
    xor_valid: bool | None
    hash_valid: bool | None
    check_code_valid: bool | None
    device_known: bool | None
    sequence_valid: bool | None
    fields_valid: bool | None
    cart_valid: bool | None  # business layer: product, weight range, stock, cart state


class CartEventResult(BaseModel):
    accepted: bool
    event_id: str
    transport: str
    packet_hex: str
    packet: ParsedPacketOut | None
    validation: ValidationOut
    rejection_code: str | None
    rejection_reason: str | None
    cart: CartOut


class IotEventOut(BaseModel):
    id: int
    event_id: str
    resident_id: int | None
    device_id: int | None
    sequence_number: int | None
    command: str | None
    product_code: int | None
    weight_grams: int | None
    packet_hex: str
    validation_status: str
    rejection_reason: str | None
    created_at: datetime


class DeviceOut(BaseModel):
    id: int
    device_code: str
    description: str
    last_sequence_number: int


class RemoveItemResult(BaseModel):
    """Result of DELETE /cart/items/{product_id}: one REMOVE_ITEM packet per batch."""

    accepted: bool
    events: list[CartEventResult]
    cart: CartOut
