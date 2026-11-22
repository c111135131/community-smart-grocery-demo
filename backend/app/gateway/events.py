"""Normalized application event produced from a validated packet."""
from dataclasses import dataclass

from app.gateway.packet import Command, Packet


@dataclass(frozen=True)
class NormalizedIoTEvent:
    """What the business layer receives; it never sees raw bytes."""

    device_id: int
    sequence_number: int
    command: Command
    product_code: int
    weight_grams: int


def to_normalized_event(packet: Packet) -> NormalizedIoTEvent:
    """Map a packet that already passed validation to an application event."""
    return NormalizedIoTEvent(
        device_id=packet.device_id,
        sequence_number=packet.sequence,
        command=Command(packet.command),
        product_code=packet.product_code,
        weight_grams=packet.weight_grams,
    )
