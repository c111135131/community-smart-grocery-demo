"""Custom 16-byte application packet: binary encode/decode and check code.

Layout (docs/IOT_PROTOCOL.md), all integers big-endian:

    offset  size  field
    0       2     header          0xAA 0x55
    2       2     device id       uint16
    4       2     sequence number uint16
    6       1     command         uint8
    7       2     product code    uint16   \\
    9       3     weight (grams)  uint24    |  6-byte payload
    12      1     flags           uint8    /
    13      1     XOR checksum over bytes 0..12
    14      2     hash-table signature over bytes 0..12 (keyed with a demo secret)

This module is pure serialization: it knows nothing about carts, prices or the
database. It is the application payload that, in the proposal, would travel in a
Matter Manufacturer Specific Cluster over Thread; here the transport is simulated.

SECURITY NOTE: the XOR byte and the 16-bit table signature are *educational*
integrity/replay checks only. They are NOT cryptographically secure and must not be
described as real anti-forgery or authentication.
"""
from dataclasses import dataclass
from enum import IntEnum

PACKET_LENGTH = 16
HEADER = b"\xAA\x55"
CHECKED_LENGTH = 13  # bytes 0..12 are covered by the check code

MAX_UINT8 = 0xFF
MAX_UINT16 = 0xFFFF
MAX_UINT24 = 0xFFFFFF


class Command(IntEnum):
    """Event commands (IOT_PROTOCOL.md section 3)."""

    BIND_CARD = 0x01
    ADD_ITEM = 0x02
    REMOVE_ITEM = 0x03
    CHECKOUT = 0x04
    ALERT = 0x05


def command_name(value: int) -> str:
    """Human-readable command name, tolerant of unknown values."""
    try:
        return Command(value).name
    except ValueError:
        return f"UNKNOWN_0x{value:02X}"


class PacketEncodeError(ValueError):
    """A field is outside the range its packet field can represent."""


class PacketDecodeError(ValueError):
    """A frame could not be decoded; `code` names the failed check."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Packet:
    """Parsed field values of a 16-byte frame (not yet trusted until verified)."""

    device_id: int
    sequence: int
    command: int  # raw byte: may be a value that is not a known Command
    product_code: int
    weight_grams: int
    flags: int


# --------------------------------------------------------------------------- check code

def xor_checksum(data: bytes) -> int:
    """XOR of every byte in `data` (educational; weak by design)."""
    result = 0
    for b in data:
        result ^= b
    return result


def _build_mixing_table() -> tuple[int, ...]:
    """Deterministic 256-entry table of 16-bit values (fixed-seed LCG).

    Built from integer arithmetic only, so encoder and decoder always agree on
    every platform and Python version.
    """
    state = 0x5EED1234
    table = []
    for _ in range(256):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        table.append((state >> 8) & 0xFFFF)
    return tuple(table)


_TABLE = _build_mixing_table()


def calculate_hash_table_signature(data: bytes, secret_key: bytes) -> int:
    """16-bit educational keyed signature using a lookup/mixing table.

    Processes `secret_key` then `data`: each byte selects a table entry that is
    mixed into a rotating 16-bit state. Deterministic, keyed, and *not* secure.
    """
    h = 0xA5C3
    for b in secret_key + data:
        h = ((h << 5) | (h >> 11)) & MAX_UINT16  # rotate left 5
        h ^= _TABLE[(b ^ h) & 0xFF]
        h = (h + b + 1) & MAX_UINT16
    return h


def compute_check_code(first_13_bytes: bytes, secret_key: bytes) -> bytes:
    """The 3 check bytes: [XOR][signature high][signature low]."""
    if len(first_13_bytes) != CHECKED_LENGTH:
        raise ValueError("check code covers exactly bytes 0..12")
    sig = calculate_hash_table_signature(first_13_bytes, secret_key)
    return bytes([xor_checksum(first_13_bytes)]) + sig.to_bytes(2, "big")


# --------------------------------------------------------------------------- encode

def _require_range(name: str, value: int, maximum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise PacketEncodeError(f"{name} must be an integer in 0..{maximum}, got {value!r}")


def encode_packet(
    *,
    device_id: int,
    sequence: int,
    command: int,
    product_code: int = 0,
    weight_grams: int = 0,
    flags: int = 0,
    secret_key: bytes,
) -> bytes:
    """Serialize fields into exactly 16 bytes.

    Only checks that each value fits its field. Semantic rules (e.g. "ADD_ITEM
    needs weight > 0") are the gateway's job, so tests can build invalid packets.
    """
    _require_range("device_id", device_id, MAX_UINT16)
    _require_range("sequence", sequence, MAX_UINT16)
    _require_range("command", int(command), MAX_UINT8)
    _require_range("product_code", product_code, MAX_UINT16)
    _require_range("weight_grams", weight_grams, MAX_UINT24)
    _require_range("flags", flags, MAX_UINT8)

    body = (
        HEADER
        + device_id.to_bytes(2, "big")
        + sequence.to_bytes(2, "big")
        + int(command).to_bytes(1, "big")
        + product_code.to_bytes(2, "big")
        + weight_grams.to_bytes(3, "big")
        + flags.to_bytes(1, "big")
    )
    frame = body + compute_check_code(body, secret_key)
    assert len(frame) == PACKET_LENGTH
    return frame


# --------------------------------------------------------------------------- decode

def parse_fields(frame: bytes) -> Packet:
    """Extract field values from a 16-byte frame. Does NOT verify header or check code."""
    if len(frame) != PACKET_LENGTH:
        raise PacketDecodeError("INVALID_LENGTH", f"frame must be {PACKET_LENGTH} bytes")
    return Packet(
        device_id=int.from_bytes(frame[2:4], "big"),
        sequence=int.from_bytes(frame[4:6], "big"),
        command=frame[6],
        product_code=int.from_bytes(frame[7:9], "big"),
        weight_grams=int.from_bytes(frame[9:12], "big"),
        flags=frame[12],
    )


def verify_check_code(frame: bytes, secret_key: bytes) -> tuple[bool, bool]:
    """Return (xor_ok, signature_ok) for a 16-byte frame."""
    body = frame[:CHECKED_LENGTH]
    xor_ok = frame[13] == xor_checksum(body)
    sig_ok = int.from_bytes(frame[14:16], "big") == calculate_hash_table_signature(
        body, secret_key
    )
    return xor_ok, sig_ok


def decode_packet(frame: bytes, secret_key: bytes) -> Packet:
    """Strict decode: length, header, known command and check code, or raise.

    The gateway uses the lower-level helpers so it can report every step; this is
    the simple "give me a trustworthy packet or an error" form.
    """
    if not isinstance(frame, (bytes, bytearray)):
        raise PacketDecodeError("INVALID_LENGTH", "frame must be bytes")
    frame = bytes(frame)
    if len(frame) != PACKET_LENGTH:
        raise PacketDecodeError("INVALID_LENGTH", f"frame must be {PACKET_LENGTH} bytes")
    if frame[:2] != HEADER:
        raise PacketDecodeError("INVALID_HEADER", "magic header must be 0xAA55")
    packet = parse_fields(frame)
    if packet.command not in {c.value for c in Command}:
        raise PacketDecodeError("UNSUPPORTED_COMMAND", f"unknown command 0x{packet.command:02X}")
    xor_ok, sig_ok = verify_check_code(frame, secret_key)
    if not (xor_ok and sig_ok):
        raise PacketDecodeError("CHECK_CODE_MISMATCH", "check code does not match")
    return packet
