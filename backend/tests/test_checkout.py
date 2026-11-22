import pytest

from app.models import Cart, CartItem, IotEvent, Order, OrderItem, Product
from app.services import checkout_service
from tests.conftest import add_event, do_checkout, get_cart


def stock(db, code):
    db.expire_all()
    return db.query(Product).filter_by(product_code=code).one().stock_grams


def fill(client, rid):
    add_event(client, rid, code=101, grams=320)   # 60.00/kg -> 19.20
    add_event(client, rid, code=102, grams=500)   # 90.00/kg -> 45.00


# ---------------------------------------------------------------- pricing in the cart
def test_cart_total_is_calculated_by_backend(client, resident_id):
    fill(client, resident_id)
    c = get_cart(client, resident_id)
    assert [(i["product_code"], i["price_per_kg"], i["subtotal"]) for i in c["items"]] == [
        (101, "60.00", "19.20"), (102, "90.00", "45.00")]
    assert c["total_amount"] == "64.20"
    assert c["total_weight_grams"] == 820


def test_cart_uses_current_db_price(client, resident_id, db_session):
    add_event(client, resident_id, grams=1000)
    db_session.query(Product).filter_by(product_code=101).one().price_per_kg = 70
    db_session.commit()
    assert get_cart(client, resident_id)["total_amount"] == "70.00"


def test_rounding_total_equals_sum_of_lines(client, resident_id, db_session):
    db_session.query(Product).filter_by(product_code=106).one().price_per_kg = 45
    db_session.commit()
    add_event(client, resident_id, code=104, grams=333)    # 45.00 -> 14.985 -> 14.99
    add_event(client, resident_id, code=106, grams=333)
    c = get_cart(client, resident_id)
    assert [i["subtotal"] for i in c["items"]] == ["14.99", "14.99"] and c["total_amount"] == "29.98"
    r = do_checkout(client, resident_id).json()
    assert r["total_amount"] == "29.98" and sum(float(i["subtotal"]) for i in r["items"]) == pytest.approx(29.98)


# ---------------------------------------------------------------- successful payment
def test_success_creates_paid_order_and_decrements_stock(client, resident_id, db_session):
    fill(client, resident_id)
    cart_total = get_cart(client, resident_id)["total_amount"]
    r = do_checkout(client, resident_id, "SUCCESS")
    assert r.status_code == 200
    body = r.json()
    assert body["payment_status"] == "PAID"
    assert body["total_amount"] == cart_total == "64.20"          # matches backend cart calculation
    assert [(i["product_name"], i["weight_grams"], i["subtotal"]) for i in body["items"]] == [
        ("番茄", 320, "19.20"), ("青花菜", 500, "45.00")]
    assert body["cart"]["items"] == [] and body["cart"]["total_amount"] == "0.00"

    order = db_session.query(Order).one()
    assert order.payment_status == "PAID" and str(order.total_amount) == "64.20"
    assert db_session.query(OrderItem).count() == 2
    assert stock(db_session, 101) == 20000 - 320 and stock(db_session, 102) == 15000 - 500
    assert db_session.query(CartItem).count() == 0


def test_stock_change_visible_in_products_and_inventory(client, resident_id):
    fill(client, resident_id); do_checkout(client, resident_id)
    p = {x["product_code"]: x["stock_grams"] for x in client.get("/api/v1/products").json()}
    assert p[101] == 19680 and p[102] == 14500
    inv = {x["product_code"]: x["stock_grams"] for x in client.get("/api/v1/admin/inventory").json()}
    assert inv[101] == 19680


def test_second_checkout_after_success_is_409(client, resident_id, db_session):
    fill(client, resident_id); do_checkout(client, resident_id)
    r = do_checkout(client, resident_id)
    assert r.status_code == 409
    assert db_session.query(Order).count() == 1 and stock(db_session, 101) == 19680


def test_order_snapshot_survives_price_and_name_change(client, resident_id, db_session):
    fill(client, resident_id); do_checkout(client, resident_id)
    p = db_session.query(Product).filter_by(product_code=101).one()
    p.price_per_kg, p.name = 999, "改名"
    db_session.commit()
    o = client.get("/api/v1/admin/orders").json()[0]
    line = next(i for i in o["items"] if i["product_id"] == p.id)
    assert (line["product_name"], line["price_per_kg"], line["subtotal"]) == ("番茄", "60.00", "19.20")
    assert o["total_amount"] == "64.20"


# ---------------------------------------------------------------- failed payment
def test_failure_keeps_cart_and_stock_and_creates_no_paid_order(client, resident_id, db_session):
    fill(client, resident_id)
    before = get_cart(client, resident_id)
    r = do_checkout(client, resident_id, "FAILURE")
    assert r.status_code == 200
    body = r.json()
    assert body["payment_status"] == "FAILED" and body["total_amount"] == "64.20"
    assert body["cart"] == before                                     # cart preserved
    assert get_cart(client, resident_id) == before
    assert stock(db_session, 101) == 20000 and stock(db_session, 102) == 15000   # no decrement
    assert db_session.query(Order).filter_by(payment_status="PAID").count() == 0
    failed = db_session.query(Order).one()                             # kept for audit only
    assert failed.payment_status == "FAILED" and len(failed.items) == 2


def test_retry_after_failure_succeeds_once(client, resident_id, db_session):
    fill(client, resident_id)
    do_checkout(client, resident_id, "FAILURE")
    do_checkout(client, resident_id, "FAILURE")
    assert do_checkout(client, resident_id, "SUCCESS").json()["payment_status"] == "PAID"
    assert stock(db_session, 101) == 20000 - 320                       # decremented exactly once
    statuses = [o.payment_status for o in db_session.query(Order).order_by(Order.id)]
    assert statuses == ["FAILED", "FAILED", "PAID"]


# ---------------------------------------------------------------- rejected checkouts (409)
def test_empty_cart_is_409_and_creates_nothing(client, resident_id, db_session):
    r = do_checkout(client, resident_id)
    assert r.status_code == 409 and "detail" in r.json()
    assert db_session.query(Order).count() == 0


def test_stock_taken_by_another_resident_blocks_checkout(client, resident_id, resident2_id, db_session):
    db_session.query(Product).filter_by(product_code=101).one().stock_grams = 400
    db_session.commit()
    add_event(client, resident_id, grams=300); add_event(client, resident2_id, grams=300)
    assert do_checkout(client, resident_id).json()["payment_status"] == "PAID"      # stock -> 100
    r = do_checkout(client, resident2_id)
    assert r.status_code == 409 and "庫存不足" in r.json()["detail"]
    assert stock(db_session, 101) == 100                                           # never negative
    assert get_cart(client, resident2_id)["items"][0]["weight_grams"] == 300       # cart kept
    assert db_session.query(Order).count() == 1


def test_delisted_product_blocks_checkout_until_removed(client, resident_id, db_session):
    fill(client, resident_id)
    p = db_session.query(Product).filter_by(product_code=101).one()
    p.is_active = False; db_session.commit()
    assert do_checkout(client, resident_id).status_code == 409
    assert client.delete(f"/api/v1/residents/{resident_id}/cart/items/{p.id}").status_code == 200
    assert do_checkout(client, resident_id).json()["total_amount"] == "45.00"


def test_unknown_resident_404_and_bad_payload_422(client, resident_id):
    assert do_checkout(client, 99999).status_code == 404
    assert do_checkout(client, resident_id, "MAYBE").status_code == 422
    assert client.post(f"/api/v1/residents/{resident_id}/checkout", json={}).status_code == 422


def test_residents_are_isolated(client, resident_id, resident2_id):
    fill(client, resident_id); add_event(client, resident2_id, code=103, grams=200)
    do_checkout(client, resident_id)
    assert get_cart(client, resident2_id)["total_amount"] == "16.00"


# ---------------------------------------------------------------- atomicity
def test_error_mid_checkout_rolls_everything_back(client, resident_id, db_session, monkeypatch):
    fill(client, resident_id)
    real = checkout_service._decrement_stock

    def boom(lines):
        real(lines)                      # stock already changed in the session ...
        raise RuntimeError("simulated crash before commit")

    monkeypatch.setattr(checkout_service, "_decrement_stock", boom)
    with pytest.raises(RuntimeError):
        do_checkout(client, resident_id)
    monkeypatch.undo()

    db_session.expire_all()
    assert db_session.query(Order).count() == 0 and db_session.query(OrderItem).count() == 0
    assert stock(db_session, 101) == 20000 and stock(db_session, 102) == 15000
    assert get_cart(client, resident_id)["total_amount"] == "64.20"
    assert do_checkout(client, resident_id).json()["payment_status"] == "PAID"   # still works


# ---------------------------------------------------------------- admin orders
def test_admin_orders_lists_paid_and_failed_newest_first(client, resident_id, resident2_id):
    fill(client, resident_id); do_checkout(client, resident_id, "FAILURE"); do_checkout(client, resident_id)
    add_event(client, resident2_id, code=103, grams=200); do_checkout(client, resident2_id)
    orders = client.get("/api/v1/admin/orders").json()
    assert [(o["payment_status"], o["resident_name"]) for o in orders] == [
        ("PAID", "Demo Resident 2"), ("PAID", "Demo Resident"), ("FAILED", "Demo Resident")]
    assert orders[0]["total_amount"] == "16.00" and orders[0]["items"][0]["product_name"] == "菠菜"
    assert len(client.get("/api/v1/admin/orders?limit=1").json()) == 1
    assert client.get("/api/v1/admin/orders?limit=0").status_code == 422


def test_checkout_does_not_touch_iot_audit(client, resident_id, db_session):
    fill(client, resident_id)
    n = db_session.query(IotEvent).count()
    do_checkout(client, resident_id)
    assert db_session.query(IotEvent).count() == n
    assert db_session.query(Cart).count() == 1                        # cart row kept, items removed
