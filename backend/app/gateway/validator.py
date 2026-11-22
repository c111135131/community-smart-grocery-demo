"""Gateway packet validator, following docs/IOT_PROTOCOL.md section 7.

Validation order (stops at the first failure; later checks stay None = "not run"):
  1. input type and exact length (16 bytes)
  2. magic header
  3. parse fields
  4. supported command
  5. XOR and keyed hash check code
  6. device known + sequence number is newer than the last accepted one
  7. command-specific field constraints
Only then is the packet mapped to a normalized event for the business layer.

This module is independent of the database and cart logic: device state is supplied
through a callback, and persistence is the caller's job.
"""
from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import StrEnum

from app.gateway.packet import (
    HEADER,
    PACKET_LENGTH,
    Command,
    Packet,
    command_name,
    parse_fields,
    verify_check_code,
)


class RejectionCode(StrEnum):
    INVALID_LENGTH = "INVALID_LENGTH"
    INVALID_HEADER = "INVALID_HEADER"
    UNSUPPORTED_COMMAND = "UNSUPPORTED_COMMAND"
    CHECK_CODE_MISMATCH = "CHECK_CODE_MISMATCH"
    UNKNOWN_DEVICE = "UNKNOWN_DEVICE"
    SEQUENCE_REPLAY = "SEQUENCE_REPLAY"
    INVALID_FIELDS = "INVALID_FIELDS"


# Commands the gateway turns into cart events in this phase.
CART_COMMANDS: frozenset[Command] = frozenset({Command.ADD_ITEM, Command.REMOVE_ITEM})

# Returns the last accepted sequence number of a device, or None if the device is unknown.
LastSequenceLookup = Callable[[int], int | None]


@dataclass
class ValidationReport:
    """Outcome of every validation step. None means the step was never reached."""

    length_valid: bool | None = None
    header_valid: bool | None = None
    command_valid: bool | None = None
    xor_valid: bool | None = None
    hash_valid: bool | None = None
    device_known: bool | None = None
    sequence_valid: bool | None = None
    fields_valid: bool | None = None
    packet: Packet | None = None
    rejection_code: RejectionCode | None = None
    rejection_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.rejection_code is None

    @property
    def check_code_valid(self) -> bool | None:
        if self.xor_valid is None or self.hash_valid is None:
            return None
        return self.xor_valid and self.hash_valid


def _reject(report: ValidationReport, code: RejectionCode, reason: str) -> ValidationReport:
    report.rejection_code = code
    report.rejection_reason = reason
    return report


def validate_frame(
    frame: object,
    *,
    secret_key: bytes,
    last_sequence_lookup: LastSequenceLookup,
    supported_commands: Collection[Command] = CART_COMMANDS,
) -> ValidationReport:
    """Validate one received frame. Never raises for bad input; returns a report."""
    report = ValidationReport()

    # 1. type and length
    if not isinstance(frame, (bytes, bytearray)) or len(frame) != PACKET_LENGTH:
        report.length_valid = False
        got = len(frame) if isinstance(frame, (bytes, bytearray)) else type(frame).__name__
        return _reject(
            report, RejectionCode.INVALID_LENGTH,
            f"frame must be exactly {PACKET_LENGTH} bytes, got {got}",
        )
    frame = bytes(frame)
    report.length_valid = True

    # 2. magic header
    report.header_valid = frame[:2] == HEADER
    if not report.header_valid:
        return _reject(
            report, RejectionCode.INVALID_HEADER,
            f"header must be 0xAA55, got 0x{frame[:2].hex().upper()}",
        )

    # 3. parse fields
    packet = parse_fields(frame)
    report.packet = packet

    # 4. supported command
    report.command_valid = packet.command in {c.value for c in supported_commands}
    if not report.command_valid:
        return _reject(
            report, RejectionCode.UNSUPPORTED_COMMAND,
            f"command {command_name(packet.command)} is not supported by the gateway",
        )

    # 5. check code (both parts are evaluated so the UI can show each)
    report.xor_valid, report.hash_valid = verify_check_code(frame, secret_key)
    if not (report.xor_valid and report.hash_valid):
        return _reject(
            report, RejectionCode.CHECK_CODE_MISMATCH,
            "check code mismatch (packet corrupted or modified)",
        )

    # 6. device state + sequence number (replay check)
    last = last_sequence_lookup(packet.device_id)
    report.device_known = last is not None
    if last is None:
        return _reject(
            report, RejectionCode.UNKNOWN_DEVICE, f"unknown device id {packet.device_id}"
        )
    report.sequence_valid = packet.sequence > last
    if not report.sequence_valid:
        return _reject(
            report, RejectionCode.SEQUENCE_REPLAY,
            f"sequence {packet.sequence} is not newer than last accepted {last} (replay)",
        )

    # 7. command-specific field constraints
    problem = _field_problem(packet)
    report.fields_valid = problem is None
    if problem is not None:
        return _reject(report, RejectionCode.INVALID_FIELDS, problem)

    return report


def _field_problem(packet: Packet) -> str | None:
    """Constraints for ADD_ITEM / REMOVE_ITEM; returns a message or None if fine."""
    if packet.command in CART_COMMANDS:
        if packet.product_code == 0:
            return "product code is required (must be > 0)"
        if packet.weight_grams == 0:
            return "weight is required (must be > 0 grams)"
        if packet.flags != 0:
            return "flags are reserved and must be 0 in this version"
    return None
