"""Simulated smart-scale device.

Only produces packets. It has no knowledge of prices, carts or inventory (see
docs/ARCHITECTURE.md, "Simulator: generate sensor-like events; no business pricing").
"""
from app.gateway.packet import Command, encode_packet


class DeviceSimulator:
    def __init__(self, device_id: int, secret_key: bytes) -> None:
        self.device_id = device_id
        self._secret_key = secret_key

    def build_packet(
        self,
        *,
        sequence: int,
        command: Command,
        product_code: int,
        weight_grams: int,
    ) -> bytes:
        """Encode one sensor event into the 16-byte frame."""
        return encode_packet(
            device_id=self.device_id,
            sequence=sequence,
            command=command,
            product_code=product_code,
            weight_grams=weight_grams,
            secret_key=self._secret_key,
        )
