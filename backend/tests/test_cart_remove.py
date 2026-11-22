from app.models import Device, IotEvent, Product
from tests.conftest import add_event, get_cart

DEL = "/api/v1/residents/{rid}/cart/items/{pid}"


def pid(db, code):
    return db.query(Product).filter_by(product_code=code).one().id


def delete(client, rid, product_id, **params):
    return client.delete(DEL.format(rid=rid, pid=product_id), params=params)


def test_delete_removes_line_via_gateway_packet(client, resident_id, db_session):
    add_event(client, resident_id, grams=300)
    r = delete(client, resident_id, pid(db_session, 101))
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True and len(body["events"]) == 1
    ev = body["events"][0]
    assert ev["packet"]["command"] == "REMOVE_ITEM" and ev["packet"]["weight_grams"] == 300
    assert len(ev["packet_hex"]) == 32 and ev["validation"]["check_code_valid"] is True
    assert body["cart"]["items"] == [] and body["cart"]["total_amount"] == "0.00"
    assert get_cart(client, resident_id)["items"] == []
    rows = db_session.query(IotEvent).order_by(IotEvent.id).all()      # audited like any event
    assert [(r.command, r.validation_status) for r in rows] == [
        ("ADD_ITEM", "ACCEPTED"), ("REMOVE_ITEM", "ACCEPTED")]


def test_delete_batches_large_weight_into_several_packets(client, resident_id, db_session):
    add_event(client, resident_id, grams=5000)
    add_event(client, resident_id, grams=5000)
    add_event(client, resident_id, grams=1234)
    body = delete(client, resident_id, pid(db_session, 101)).json()
    assert [e["packet"]["weight_grams"] for e in body["events"]] == [5000, 5000, 1234]
    assert [e["packet"]["sequence_number"] for e in body["events"]] == [3, 4, 5]
    assert body["accepted"] is True and body["cart"]["items"] == []


def test_small_remainder_can_be_removed(client, resident_id, db_session):
    add_event(client, resident_id, grams=300)
    assert add_event(client, resident_id, "REMOVE_ITEM", grams=270).status_code == 200   # leaves 30 g
    assert get_cart(client, resident_id)["items"][0]["weight_grams"] == 30
    assert delete(client, resident_id, pid(db_session, 101)).status_code == 200
    assert get_cart(client, resident_id)["items"] == []


def test_remove_event_above_product_max_is_400(client, resident_id):
    for _ in range(2):
        add_event(client, resident_id, grams=5000)
    r = add_event(client, resident_id, "REMOVE_ITEM", grams=6000)
    assert r.status_code == 400 and r.json()["rejection_code"] == "WEIGHT_OUT_OF_RANGE"
    assert get_cart(client, resident_id)["items"][0]["weight_grams"] == 10000


def test_add_below_minimum_still_rejected(client, resident_id):
    assert add_event(client, resident_id, grams=30).json()["rejection_code"] == "WEIGHT_OUT_OF_RANGE"


def test_delete_keeps_other_lines_and_updates_totals(client, resident_id, db_session):
    add_event(client, resident_id, code=101, grams=320)
    add_event(client, resident_id, code=102, grams=500)
    body = delete(client, resident_id, pid(db_session, 101)).json()
    assert [i["product_code"] for i in body["cart"]["items"]] == [102]
    assert body["cart"]["total_amount"] == "45.00"


def test_delete_not_in_cart_is_409(client, resident_id, db_session):
    assert delete(client, resident_id, pid(db_session, 101)).status_code == 409


def test_delete_unknown_product_resident_or_device_404(client, resident_id, db_session):
    assert delete(client, resident_id, 99999).status_code == 404
    assert delete(client, 99999, pid(db_session, 101)).status_code == 404
    add_event(client, resident_id)
    assert delete(client, resident_id, pid(db_session, 101), device_id=42).status_code == 404
    assert get_cart(client, resident_id)["items"][0]["weight_grams"] == 320   # untouched


def test_delete_only_touches_own_cart(client, resident_id, resident2_id, db_session):
    add_event(client, resident_id); add_event(client, resident2_id)
    delete(client, resident_id, pid(db_session, 101))
    assert get_cart(client, resident2_id)["items"][0]["weight_grams"] == 320


def test_delisted_product_can_still_be_removed_from_cart(client, resident_id, db_session):
    add_event(client, resident_id)
    db_session.query(Product).filter_by(product_code=101).one().is_active = False
    db_session.commit()
    assert delete(client, resident_id, pid(db_session, 101)).status_code == 200
    assert get_cart(client, resident_id)["items"] == []


def test_delete_consumes_sequence_numbers(client, resident_id, db_session):
    add_event(client, resident_id)                       # seq 0
    delete(client, resident_id, pid(db_session, 101))    # seq 1
    db_session.expire_all()
    assert db_session.query(Device).one().last_sequence_number == 1
