from app.models import Product


def test_list_products_has_at_least_five_with_unique_codes(client):
    items = client.get("/api/v1/products").json()
    assert len(items) >= 5
    codes = [p["product_code"] for p in items]
    assert len(codes) == len(set(codes))


def test_product_fields_and_money_format(client):
    tomato = next(p for p in client.get("/api/v1/products").json() if p["product_code"] == 101)
    assert tomato["name"] == "番茄"
    assert tomato["price_per_kg"] == "60.00"  # Decimal serialized as string, not float
    assert isinstance(tomato["stock_grams"], int)
    assert tomato["nutrition"]["summary"]
    assert tomato["nutrition"]["per_100g"]["sodium_mg"] == 5


def test_product_codes_fit_uint16(client):
    for p in client.get("/api/v1/products").json():
        assert 0 <= p["product_code"] <= 65535


def test_get_product_detail(client):
    first = client.get("/api/v1/products").json()[0]
    resp = client.get(f"/api/v1/products/{first['id']}")
    assert resp.status_code == 200
    assert resp.json()["product_code"] == first["product_code"]


def test_get_unknown_product_is_404(client):
    assert client.get("/api/v1/products/99999").status_code == 404


def test_inactive_product_hidden_from_listing_but_shown_in_admin(client, db_session):
    p = db_session.query(Product).filter_by(product_code=108).one()
    p.is_active = False
    db_session.commit()

    listed = [x["product_code"] for x in client.get("/api/v1/products").json()]
    assert 108 not in listed
    assert client.get(f"/api/v1/products/{p.id}").status_code == 404

    inventory = client.get("/api/v1/admin/inventory").json()
    row = next(x for x in inventory if x["product_code"] == 108)
    assert row["is_active"] is False


def test_admin_inventory_lists_all_products(client):
    assert len(client.get("/api/v1/admin/inventory").json()) >= 5
