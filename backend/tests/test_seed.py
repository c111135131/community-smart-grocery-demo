from app.models import Device, HealthProfile, Product, Resident
from app.seed import seed


def test_seed_is_idempotent(db_session):
    counts_before = (
        db_session.query(Resident).count(),
        db_session.query(Product).count(),
        db_session.query(Device).count(),
    )
    created = seed(db_session)
    assert created == {"residents": 0, "products": 0, "devices": 0}
    assert counts_before == (
        db_session.query(Resident).count(),
        db_session.query(Product).count(),
        db_session.query(Device).count(),
    )


def test_seed_does_not_overwrite_changed_stock(db_session):
    p = db_session.query(Product).filter_by(product_code=101).one()
    p.stock_grams = 123
    db_session.commit()
    seed(db_session)
    assert db_session.query(Product).filter_by(product_code=101).one().stock_grams == 123


def test_seed_content_matches_docs(db_session):
    cards = {r.card_id for r in db_session.query(Resident)}
    assert {"CARD-1001", "CARD-1002"} <= cards
    assert db_session.query(HealthProfile).count() == 2
    assert 5 <= db_session.query(Product).count() <= 8
    device = db_session.query(Device).one()
    assert device.last_sequence_number == -1
