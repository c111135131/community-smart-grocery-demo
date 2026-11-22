import pytest

from app.gateway.packet import Command
from app.gateway.validator import RejectionCode as RC
from app.gateway.validator import validate_frame
from tests.conftest import KEY, make_frame


def run(frame, last=-1, known=True):
    return validate_frame(
        frame, secret_key=KEY,
        last_sequence_lookup=lambda d: last if known else None,
    )


def test_valid_packet_passes_every_step():
    r = run(make_frame(sequence=0))
    assert r.accepted and r.rejection_code is None
    assert all(v is True for v in (
        r.length_valid, r.header_valid, r.command_valid, r.xor_valid, r.hash_valid,
        r.check_code_valid, r.device_known, r.sequence_valid, r.fields_valid))
    assert r.packet.product_code == 101


@pytest.mark.parametrize("frame", [b"", b"\xAA\x55", make_frame()[:15], make_frame() + b"\x00", "not bytes", None])
def test_wrong_length_or_type_rejected(frame):
    r = run(frame)
    assert r.rejection_code == RC.INVALID_LENGTH and r.length_valid is False
    assert r.header_valid is None and r.packet is None


def test_wrong_header_rejected_and_not_parsed():
    r = run(b"\x00\x00" + make_frame()[2:])
    assert r.rejection_code == RC.INVALID_HEADER and r.header_valid is False
    assert r.packet is None and r.command_valid is None


@pytest.mark.parametrize("cmd", [0x7F, 0x00, int(Command.BIND_CARD), int(Command.CHECKOUT), int(Command.ALERT)])
def test_unsupported_command_rejected(cmd):
    r = run(make_frame(command=cmd))
    assert r.rejection_code == RC.UNSUPPORTED_COMMAND and r.command_valid is False
    assert r.packet is not None  # fields parsed, so audit can record them


@pytest.mark.parametrize("index", [7, 8, 9, 10, 11])  # payload bytes
def test_tampered_payload_fails_check_code(index):
    f = bytearray(make_frame())
    f[index] ^= 0x01
    r = run(bytes(f))
    assert r.rejection_code == RC.CHECK_CODE_MISMATCH
    assert r.xor_valid is False
    assert r.hash_valid is False
    assert r.sequence_valid is None  # later steps not reached


def test_tampered_signature_only_flags_hash():
    f = bytearray(make_frame())
    f[15] ^= 0xFF
    r = run(bytes(f))
    assert r.rejection_code == RC.CHECK_CODE_MISMATCH
    assert r.xor_valid is True and r.hash_valid is False


def test_wrong_key_rejected():
    r = validate_frame(make_frame(), secret_key=b"other", last_sequence_lookup=lambda d: -1)
    assert r.rejection_code == RC.CHECK_CODE_MISMATCH


def test_unknown_device_rejected():
    r = run(make_frame(device_id=999), known=False)
    assert r.rejection_code == RC.UNKNOWN_DEVICE and r.device_known is False


@pytest.mark.parametrize("seq,last", [(5, 5), (4, 5), (0, 0)])
def test_replayed_or_old_sequence_rejected(seq, last):
    r = run(make_frame(sequence=seq), last=last)
    assert r.rejection_code == RC.SEQUENCE_REPLAY and r.sequence_valid is False
    assert r.fields_valid is None


def test_newer_sequence_accepted_even_with_gap():
    assert run(make_frame(sequence=10), last=5).accepted


@pytest.mark.parametrize("kw", [{"weight_grams": 0}, {"product_code": 0}, {"flags": 1}])
def test_invalid_fields_rejected(kw):
    r = run(make_frame(**kw))
    assert r.rejection_code == RC.INVALID_FIELDS and r.fields_valid is False


def test_validation_order_is_respected():
    # bad header AND bad check code -> header is reported first
    f = bytearray(make_frame()); f[0] = 0; f[11] ^= 1
    assert run(bytes(f)).rejection_code == RC.INVALID_HEADER
    # bad check code AND replayed sequence -> check code first (no state is consulted)
    f = bytearray(make_frame(sequence=1)); f[11] ^= 1
    assert run(bytes(f), last=5).rejection_code == RC.CHECK_CODE_MISMATCH
    # replayed sequence AND invalid weight -> replay first
    assert run(make_frame(sequence=1, weight_grams=0), last=5).rejection_code == RC.SEQUENCE_REPLAY


def test_validator_does_not_consult_device_state_before_check_code():
    called = []
    f = bytearray(make_frame()); f[11] ^= 1
    validate_frame(bytes(f), secret_key=KEY, last_sequence_lookup=lambda d: called.append(d) or -1)
    assert called == []
