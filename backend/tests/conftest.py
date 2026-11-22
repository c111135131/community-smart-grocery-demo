"""Test fixtures: isolated in-memory SQLite DB seeded with demo data.

Unit tests need no external services. Migration + PostgreSQL behaviour is
verified separately (see README, "Verify against PostgreSQL").
"""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base
from app.seed import seed


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- Phase 2 helpers -------------------------------------------------------
from app.core.config import get_settings  # noqa: E402
from app.gateway.packet import Command, encode_packet  # noqa: E402

KEY = get_settings().iot_secret_key.encode()


def make_frame(
    *, device_id=1, sequence=0, command=Command.ADD_ITEM, product_code=101,
    weight_grams=320, flags=0,
) -> bytes:
    return encode_packet(
        device_id=device_id, sequence=sequence, command=command,
        product_code=product_code, weight_grams=weight_grams, flags=flags, secret_key=KEY,
    )


@pytest.fixture()
def resident_id(client) -> int:
    return client.post("/api/v1/residents/login", json={"card_id": "CARD-1001"}).json()["resident_id"]


# ---- Phase 3 helpers -------------------------------------------------------
def add_event(client, rid, command="ADD_ITEM", code=101, grams=320, device_id=1):
    return client.post(f"/api/v1/residents/{rid}/cart/events", json={
        "device_id": device_id, "command": command, "product_code": code, "weight_grams": grams})


def get_cart(client, rid):
    return client.get(f"/api/v1/residents/{rid}/cart").json()


def do_checkout(client, rid, sim="SUCCESS"):
    return client.post(f"/api/v1/residents/{rid}/checkout", json={"payment_simulation": sim})


@pytest.fixture()
def resident2_id(client) -> int:
    return client.post("/api/v1/residents/login", json={"card_id": "CARD-1002"}).json()["resident_id"]
