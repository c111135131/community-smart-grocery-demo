def test_login_card_1001_returns_profile(client):
    resp = client.post("/api/v1/residents/login", json={"card_id": "CARD-1001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Demo Resident"
    assert body["health_profile"]["dietary_preferences"] == ["low_sodium"]
    assert body["health_profile"]["allergies"] == []


def test_login_card_1002_has_vegetarian_preference(client):
    body = client.post("/api/v1/residents/login", json={"card_id": "CARD-1002"}).json()
    assert body["health_profile"]["dietary_preferences"] == ["vegetarian"]


def test_login_strips_whitespace(client):
    resp = client.post("/api/v1/residents/login", json={"card_id": "  CARD-1001 "})
    assert resp.status_code == 200


def test_login_unknown_card_is_401(client):
    resp = client.post("/api/v1/residents/login", json={"card_id": "CARD-9999"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_login_blank_or_missing_card_is_422(client):
    assert client.post("/api/v1/residents/login", json={"card_id": "   "}).status_code == 422
    assert client.post("/api/v1/residents/login", json={}).status_code == 422
    assert client.post("/api/v1/residents/login", json={"card_id": "X" * 33}).status_code == 422


def test_get_resident_by_id(client):
    rid = client.post("/api/v1/residents/login", json={"card_id": "CARD-1001"}).json()["resident_id"]
    resp = client.get(f"/api/v1/residents/{rid}")
    assert resp.status_code == 200
    assert resp.json()["resident_id"] == rid


def test_get_unknown_resident_is_404(client):
    assert client.get("/api/v1/residents/99999").status_code == 404


def test_login_response_does_not_expose_card_id(client):
    body = client.post("/api/v1/residents/login", json={"card_id": "CARD-1001"}).json()
    assert "card_id" not in body
