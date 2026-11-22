import pytest

from app.models import Device, IotEvent, Product
from tests.conftest import make_frame

EV = "/api/v1/residents/{rid}/cart/events"
PK = "/api/v1/residents/{rid}/cart/packets"


def add(client, rid, code=101, grams=320, command="ADD_ITEM", device_id=1):
    return client.post(EV.format(rid=rid), json={
        "device_id": device_id, "command": command, "product_code": code, "weight_grams": grams})


def raw(client, rid, frame):
    hexs = frame.hex() if isinstance(frame, bytes) else frame
    return client.post(PK.format(rid=rid), json={"packet_hex": hexs})


def cart(client, rid):
    return client.get(f"/api/v1/residents/{rid}/cart").json()


def device(db):
    db.expire_all()
    return db.query(Device).filter_by(id=1).one()


# ---------------------------------------------------------------- happy path
def test_valid_event_updates_cart_through_gateway(client, resident_id):
    r = add(client, resident_id)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert len(body["packet_hex"]) == 32                      # 16 bytes
    assert body["packet_hex"].startswith("AA55")
    assert body["packet"]["command"] == "ADD_ITEM"
    assert body["packet"]["sequence_number"] == 0
    assert body["validation"]["check_code_valid"] is True
    assert body["validation"]["cart_valid"] is True
    assert "SIMULATED" in body["transport"]
    assert body["cart"]["items"] == [
        {"product_id": body["cart"]["items"][0]["product_id"], "product_code": 101,
         "name": "番茄", "weight_grams": 320, "price_per_kg": "60.00", "subtotal": "19.20"}]
    assert body["cart"]["total_amount"] == "19.20"
    assert cart(client, resident_id)["total_weight_grams"] == 320


def test_sequence_advances_and_weights_accumulate(client, resident_id, db_session):
    add(client, resident_id, grams=300)
    r = add(client, resident_id, grams=200)
    assert r.json()["packet"]["sequence_number"] == 1
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 500
    assert device(db_session).last_sequence_number == 1


def test_multiple_products(client, resident_id):
    add(client, resident_id, code=101, grams=300)
    add(client, resident_id, code=107, grams=500)
    c = cart(client, resident_id)
    assert [i["product_code"] for i in c["items"]] == [101, 107]
    assert c["total_weight_grams"] == 800


def test_carts_are_per_resident(client, resident_id):
    other = client.post("/api/v1/residents/login", json={"card_id": "CARD-1002"}).json()["resident_id"]
    add(client, resident_id, grams=300)
    assert cart(client, other)["items"] == []


def test_empty_cart_for_new_resident(client, resident_id):
    assert cart(client, resident_id) == {"items": [], "total_weight_grams": 0, "total_amount": "0.00"}


# ---------------------------------------------------------------- remove
def test_remove_partial_then_full(client, resident_id):
    add(client, resident_id, grams=500)
    assert add(client, resident_id, grams=200, command="REMOVE_ITEM").status_code == 200
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 300
    assert add(client, resident_id, grams=300, command="REMOVE_ITEM").status_code == 200
    assert cart(client, resident_id)["items"] == []


def test_remove_item_not_in_cart_is_409_and_cart_unchanged(client, resident_id):
    r = add(client, resident_id, command="REMOVE_ITEM")
    assert r.status_code == 409
    assert r.json()["rejection_code"] == "ITEM_NOT_IN_CART"
    assert r.json()["validation"]["cart_valid"] is False
    assert cart(client, resident_id)["items"] == []


def test_remove_more_than_in_cart_is_409_and_cart_unchanged(client, resident_id):
    add(client, resident_id, grams=300)
    r = add(client, resident_id, grams=400, command="REMOVE_ITEM")
    assert r.status_code == 409 and r.json()["rejection_code"] == "REMOVE_EXCEEDS_CART"
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 300


# ---------------------------------------------------------------- business rejections
def test_unknown_product_404_cart_unchanged_and_audited(client, resident_id, db_session):
    r = add(client, resident_id, code=999)
    assert r.status_code == 404 and r.json()["rejection_code"] == "PRODUCT_NOT_FOUND"
    assert cart(client, resident_id)["items"] == []
    row = db_session.query(IotEvent).one()
    assert row.validation_status == "REJECTED" and "PRODUCT_NOT_FOUND" in row.rejection_reason


@pytest.mark.parametrize("grams", [10, 6000])
def test_weight_outside_product_range_is_400(client, resident_id, grams):
    r = add(client, resident_id, grams=grams)
    assert r.status_code == 400 and r.json()["rejection_code"] == "WEIGHT_OUT_OF_RANGE"
    assert cart(client, resident_id)["items"] == []


def test_exceeding_stock_is_409(client, resident_id, db_session):
    db_session.query(Product).filter_by(product_code=101).one().stock_grams = 400
    db_session.commit()
    assert add(client, resident_id, grams=300).status_code == 200
    r = add(client, resident_id, grams=300)
    assert r.status_code == 409 and r.json()["rejection_code"] == "INSUFFICIENT_STOCK"
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 300


def test_inactive_product_rejected(client, resident_id, db_session):
    db_session.query(Product).filter_by(product_code=101).one().is_active = False
    db_session.commit()
    assert add(client, resident_id).json()["rejection_code"] == "PRODUCT_NOT_FOUND"


def test_sequence_consumed_when_gateway_ok_but_cart_rejects(client, resident_id, db_session):
    add(client, resident_id, code=999)                       # seq 0, business reject
    assert device(db_session).last_sequence_number == 0
    assert add(client, resident_id).json()["packet"]["sequence_number"] == 1


# ---------------------------------------------------------------- replay / tamper / malformed
def test_replayed_packet_rejected_cart_unchanged(client, resident_id, db_session):
    first = add(client, resident_id, grams=300).json()
    r = raw(client, resident_id, first["packet_hex"])        # exact same bytes again
    assert r.status_code == 409
    body = r.json()
    assert body["accepted"] is False and body["rejection_code"] == "SEQUENCE_REPLAY"
    assert body["validation"]["check_code_valid"] is True    # authentic ...
    assert body["validation"]["sequence_valid"] is False     # ... but old
    assert body["packet_hex"] == first["packet_hex"]
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 300
    assert device(db_session).last_sequence_number == 0


def test_old_sequence_rejected_after_newer_accepted(client, resident_id):
    add(client, resident_id); add(client, resident_id)       # seq 0, 1
    r = raw(client, resident_id, make_frame(sequence=0))
    assert r.status_code == 409 and r.json()["rejection_code"] == "SEQUENCE_REPLAY"


def test_tampered_packet_rejected_sequence_not_advanced(client, resident_id, db_session):
    first = add(client, resident_id, grams=300).json()
    b = bytearray(bytes.fromhex(first["packet_hex"]))
    b[4:6] = (5).to_bytes(2, "big")                          # fresh sequence ...
    b[11] ^= 0x01                                            # ... but payload altered, code stale
    r = raw(client, resident_id, bytes(b))
    assert r.status_code == 400 and r.json()["rejection_code"] == "CHECK_CODE_MISMATCH"
    assert r.json()["validation"]["xor_valid"] is False
    assert cart(client, resident_id)["items"][0]["weight_grams"] == 300
    assert device(db_session).last_sequence_number == 0


@pytest.mark.parametrize("frame,code,status", [
    (make_frame()[:15], "INVALID_LENGTH", 400),
    (make_frame() + b"\x00", "INVALID_LENGTH", 400),
    (b"\x00\x00" + make_frame()[2:], "INVALID_HEADER", 400),
    (make_frame(command=0x7F), "UNSUPPORTED_COMMAND", 400),
    (make_frame(device_id=999), "UNKNOWN_DEVICE", 400),
    (make_frame(weight_grams=0), "INVALID_FIELDS", 400),
    (make_frame(product_code=0), "INVALID_FIELDS", 400),
])
def test_malformed_packets_rejected_with_no_side_effects(client, resident_id, db_session, frame, code, status):
    r = raw(client, resident_id, frame)
    assert r.status_code == status and r.json()["rejection_code"] == code
    assert cart(client, resident_id)["items"] == []
    assert device(db_session).last_sequence_number == -1


def test_checkout_command_not_supported_in_this_phase(client, resident_id):
    r = add(client, resident_id, command="CHECKOUT")
    assert r.status_code == 400 and r.json()["rejection_code"] == "UNSUPPORTED_COMMAND"


# ---------------------------------------------------------------- audit
def test_every_frame_is_audited_with_packet_hex(client, resident_id, db_session):
    ok = add(client, resident_id).json()
    raw(client, resident_id, ok["packet_hex"])               # replay
    raw(client, resident_id, make_frame()[:15])              # malformed length
    raw(client, resident_id, b"\x00\x00" + make_frame()[2:]) # bad header
    rows = db_session.query(IotEvent).order_by(IotEvent.id).all()
    assert [r.validation_status for r in rows] == ["ACCEPTED", "REJECTED", "REJECTED", "REJECTED"]
    assert rows[0].packet_hex == ok["packet_hex"] and rows[0].sequence_number == 0
    assert rows[0].device_id == 1 and rows[0].command == "ADD_ITEM"
    assert rows[1].rejection_reason.startswith("SEQUENCE_REPLAY")
    assert rows[2].device_id is None and rows[2].command is None   # unparseable
    assert len(rows[2].packet_hex) == 30
    assert all(r.resident_id == resident_id for r in rows)


def test_unknown_device_audit_has_no_device_fk(client, resident_id, db_session):
    raw(client, resident_id, make_frame(device_id=999))
    row = db_session.query(IotEvent).one()
    assert row.device_id is None and row.sequence_number == 0 and "UNKNOWN_DEVICE" in row.rejection_reason


def test_admin_audit_and_device_endpoints(client, resident_id):
    ok = add(client, resident_id).json()
    raw(client, resident_id, ok["packet_hex"])
    events = client.get("/api/v1/admin/iot-events").json()
    assert [e["validation_status"] for e in events] == ["REJECTED", "ACCEPTED"]  # newest first
    assert events[1]["event_id"] == ok["event_id"]
    devs = client.get("/api/v1/admin/devices").json()
    assert devs[0]["device_code"] == "DEV-001" and devs[0]["last_sequence_number"] == 0
    assert client.get("/api/v1/admin/iot-events?limit=0").status_code == 422


# ---------------------------------------------------------------- request validation
def test_unknown_resident_404(client):
    assert add(client, 99999).status_code == 404
    assert raw(client, 99999, make_frame()).status_code == 404
    assert client.get("/api/v1/residents/99999/cart").status_code == 404


def test_unknown_device_on_simulated_event_404(client, resident_id):
    assert add(client, resident_id, device_id=42).status_code == 404


@pytest.mark.parametrize("payload", [
    {"device_id": 1, "command": "NOPE", "product_code": 101, "weight_grams": 100},
    {"device_id": 1, "command": "ADD_ITEM", "product_code": 70000, "weight_grams": 100},
    {"device_id": 1, "command": "ADD_ITEM", "product_code": 101, "weight_grams": -1},
    {"device_id": 1, "command": "ADD_ITEM", "product_code": 101, "weight_grams": 20000000},
    {"command": "ADD_ITEM", "product_code": 101, "weight_grams": 100},
])
def test_invalid_event_request_is_422(client, resident_id, payload):
    assert client.post(EV.format(rid=resident_id), json=payload).status_code == 422


@pytest.mark.parametrize("bad", ["", "   ", "ZZ", "AA5", "AA 55 zz", "A" * 300])
def test_invalid_hex_is_422(client, resident_id, bad):
    assert raw(client, resident_id, bad).status_code == 422


def test_hex_with_spaces_and_lowercase_and_0x_prefix_accepted(client, resident_id):
    f = make_frame(sequence=0)
    spaced = "0x" + " ".join(f.hex()[i:i + 2] for i in range(0, 32, 2))
    assert raw(client, resident_id, spaced).status_code == 200


def test_sequence_exhaustion_is_409(client, resident_id, db_session):
    device(db_session).last_sequence_number = 65535
    db_session.commit()
    assert add(client, resident_id).status_code == 409
