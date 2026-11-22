"""Device-to-gateway transport abstraction.

In the proposed architecture the 16-byte payload is carried in a Matter
Manufacturer Specific Cluster over Matter-over-Thread. This project does NOT deploy
a real Thread mesh, Border Router or Matter commissioning. `SimulatedMatterThread
Transport` hands the bytes straight to the gateway in-process. A real Matter SDK
transport could later implement `MatterTransportAdapter` without touching the
packet, validator or cart code.
"""
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

R = TypeVar("R")


class MatterTransportAdapter(ABC, Generic[R]):
    """Carries one opaque frame from a device to the gateway."""

    #: Shown in API responses/UI so nobody mistakes the simulation for real hardware.
    description: str

    @abstractmethod
    def send(self, frame: bytes) -> R:
        """Deliver `frame` unchanged to the gateway and return its handler result."""


class SimulatedMatterThreadTransport(MatterTransportAdapter[R]):
    """SOFTWARE SIMULATION of the Matter-over-Thread device->gateway path."""

    description = "SIMULATED Matter-over-Thread (in-process software adapter, no real Thread mesh)"

    def __init__(self, gateway_handler: Callable[[bytes], R]) -> None:
        self._handler = gateway_handler

    def send(self, frame: bytes) -> R:
        # Deliberately no validation here: a transport only moves bytes. Malformed
        # frames must reach the gateway so it can reject and audit them.
        return self._handler(frame)
