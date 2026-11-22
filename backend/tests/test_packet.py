import pytest

from app.gateway.packet import (
    Command, PacketDecodeError, PacketEncodeError, calculate_hash_table_signature,
    decode_packet, encode_packet, xor_checksum,
)

KEY = b"demo-secret-not-for-production"
# Golden vector: device 1, seq 1, ADD_ITEM, product 101, 320 g. Locks the wire format.
GOLDEN_HEX = "AA550001000102006500014000D9847C"


def _golden() -> bytes:
    return encode_packet(device_id=1, sequence=1, command=Command.ADD_ITEM,
                         product_code=101, weight_grams=320, secret_key=KEY)


def test_encodes_to_exactly_16_bytes_matching_golden_vector():
    frame = _golden()
    assert len(frame) == 16
    assert frame.hex().upper() == GOLDEN_HEX


def test_field_layout_is_big_endian_at_documented_offsets():
    frame = _golden()
    assert frame[0:2] == b"\xAA\x55"
    assert int.from_bytes(frame[2:4], "big") == 1      # device
    assert int.from_bytes(frame[4:6], "big") == 1      # sequence
    assert frame[6] == 0x02                            # command
    assert int.from_bytes(frame[7:9], "big") == 101    # product
    assert int.from_bytes(frame[9:12], "big") == 320   # weight (uint24)
    assert frame[12] == 0                              # flags
    assert frame[13] == xor_checksum(frame[:13])


def test_round_trip():
    p = decode_packet(_golden(), KEY)
    assert (p.device_id, p.sequence, p.command, p.product_code, p.weight_grams, p.flags) == (
        1, 1, Command.ADD_ITEM, 101, 320, 0)


def test_max_values_round_trip():
    f = encode_packet(device_id=65535, sequence=65535, command=Command.ALERT,
                      product_code=65535, weight_grams=0xFFFFFF, flags=255, secret_key=KEY)
    p = decode_packet(f, KEY)
    assert (p.device_id, p.sequence, p.product_code, p.weight_grams, p.flags) == (
        65535, 65535, 65535, 0xFFFFFF, 255)


@pytest.mark.parametrize("kwargs", [
    {"device_id": -1}, {"device_id": 65536}, {"sequence": 65536}, {"product_code": 65536},
    {"weight_grams": 0x1000000}, {"weight_grams": -5}, {"flags": 256}, {"command": 256},
])
def test_encode_rejects_out_of_range_fields(kwargs):
    base = dict(device_id=1, sequence=1, command=2, product_code=101, weight_grams=1,
                flags=0, secret_key=KEY)
    base.update(kwargs)
    with pytest.raises(PacketEncodeError):
        encode_packet(**base)


def test_xor_checksum():
    assert xor_checksum(b"") == 0
    assert xor_checksum(b"\x01\x02\x03") == 0x00
    assert xor_checksum(b"\xFF\x0F") == 0xF0


def test_signature_is_deterministic_and_key_dependent():
    data = _golden()[:13]
    assert calculate_hash_table_signature(data, KEY) == calculate_hash_table_signature(data, KEY)
    assert calculate_hash_table_signature(data, KEY) != calculate_hash_table_signature(data, b"other")


def test_signature_changes_when_any_covered_byte_changes():
    data = bytearray(_golden()[:13])
    base = calculate_hash_table_signature(bytes(data), KEY)
    for i in range(13):
        mutated = bytearray(data)
        mutated[i] ^= 0x01
        assert calculate_hash_table_signature(bytes(mutated), KEY) != base, f"byte {i}"


@pytest.mark.parametrize("frame,code", [
    (b"", "INVALID_LENGTH"),
    (_golden()[:15], "INVALID_LENGTH"),
    (_golden() + b"\x00", "INVALID_LENGTH"),
    (b"\x00\x00" + _golden()[2:], "INVALID_HEADER"),
])
def test_decode_errors(frame, code):
    with pytest.raises(PacketDecodeError) as e:
        decode_packet(frame, KEY)
    assert e.value.code == code


def test_decode_detects_tampering_and_wrong_key():
    tampered = bytearray(_golden())
    tampered[11] ^= 0x01
    with pytest.raises(PacketDecodeError) as e:
        decode_packet(bytes(tampered), KEY)
    assert e.value.code == "CHECK_CODE_MISMATCH"
    with pytest.raises(PacketDecodeError):
        decode_packet(_golden(), b"wrong-key")


def test_decode_unknown_command():
    f = encode_packet(device_id=1, sequence=1, command=0x7F, secret_key=KEY)
    with pytest.raises(PacketDecodeError) as e:
        decode_packet(f, KEY)
    assert e.value.code == "UNSUPPORTED_COMMAND"
