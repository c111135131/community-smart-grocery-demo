"""Failure paths and operational code that the feature tests do not reach."""
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers import AnthropicProvider, LLMRequest
from app.api.nutrition import get_provider_selection
from app.ai.providers import MockProvider, ProviderSelection
from app.core import database
from app.core.config import Settings
from app.gateway.events import NormalizedIoTEvent
from app.gateway.packet import (
    Command, PacketDecodeError, compute_check_code, decode_packet, parse_fields,
)
from app.main import app
from app.models import Base, Device, IotEvent, Product
from app.services import cart_service, iot_service
from app.wait_for_db import main as wait_main
from app.wait_for_db import wait_for_database
from tests.conftest import add_event, get_cart

BACKEND = Path(__file__).resolve().parents[1]
GOLDEN = "AA550001000102006500014000D9847C"


# ------------------------------------------------------------------ wait_for_db
def test_wait_returns_immediately_when_database_is_ready():
    sleeps = []
    assert wait_for_database(5, check=lambda: True, sleep=sleeps.append) is True
    assert sleeps == []


def test_wait_polls_until_the_database_comes_up():
    answers = iter([False, False, False, True])
    sleeps, now = [], [0.0]
    ok = wait_for_database(
        60, interval_seconds=2, check=lambda: next(answers),
        sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)), clock=lambda: now[0],
    )
    assert ok is True and sleeps == [2, 2, 2]


def test_wait_gives_up_after_the_timeout():
    now = [0.0]
    ok = wait_for_database(
        5, interval_seconds=2, check=lambda: False,
        sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0],
    )
    assert ok is False


def test_wait_cli_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["wait_for_db", "--timeout", "1"])
    monkeypatch.setattr("app.wait_for_db.wait_for_database", lambda t: True)
    wait_main()
    assert "ready" in capsys.readouterr().out
    monkeypatch.setattr("app.wait_for_db.wait_for_database", lambda t: False)
    with pytest.raises(SystemExit) as e:
        wait_main()
    assert e.value.code == 1 and "did not become ready" in capsys.readouterr().err


def test_docker_entrypoint_runs_the_documented_steps_in_order():
    script = (BACKEND / "scripts" / "docker-entrypoint.sh").read_text()
    order = [script.index(s) for s in ("app.wait_for_db", "alembic upgrade head", "app.seed", "uvicorn")]
    assert order == sorted(order)
    assert "set -e" in script and "exec uvicorn" in script and "--host 0.0.0.0" in script


# ------------------------------------------------------------------ gateway robustness
def test_unexpected_error_rolls_back_sequence_cart_and_audit(client, resident_id, db_session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated crash inside the cart service")

    monkeypatch.setattr(cart_service, "apply_event", boom)
    with pytest.raises(RuntimeError):
        add_event(client, resident_id)
    monkeypatch.undo()

    # NOTE: no expire_all() here on purpose: it would silently discard un-rolled-back changes
    # and make this test pass even without the gateway's explicit rollback.
    assert db_session.query(Device).one().last_sequence_number == -1      # sequence NOT consumed
    assert db_session.query(IotEvent).count() == 0                         # nothing half-audited
    assert get_cart(client, resident_id)["items"] == []
    ok = add_event(client, resident_id)                                    # and the system still works
    assert ok.status_code == 200 and ok.json()["packet"]["sequence_number"] == 0


def test_delete_stops_at_a_rejected_batch_and_keeps_earlier_batches(client, resident_id, db_session, monkeypatch):
    add_event(client, resident_id, grams=5000); add_event(client, resident_id, grams=5000)
    product_id = db_session.query(Product).filter_by(product_code=101).one().id
    real, calls = iot_service.submit_simulated_event, []

    def flaky(db, rid, request):
        calls.append(request.weight_grams)
        result = real(db, rid, request)
        if len(calls) == 2:      # pretend the 2nd batch was refused after the 1st succeeded
            return result.model_copy(update={"accepted": False, "rejection_code": "WEIGHT_OUT_OF_RANGE"})
        return result

    monkeypatch.setattr(iot_service, "submit_simulated_event", flaky)
    r = client.delete(f"/api/v1/residents/{resident_id}/cart/items/{product_id}")
    assert r.status_code == 400 and r.json()["accepted"] is False and len(r.json()["events"]) == 2
    assert calls == [5000, 5000]


def test_delete_with_exhausted_device_sequence_is_409(client, resident_id, db_session):
    add_event(client, resident_id)
    db_session.query(Device).one().last_sequence_number = 65535
    db_session.commit()
    pid = db_session.query(Product).filter_by(product_code=101).one().id
    r = client.delete(f"/api/v1/residents/{resident_id}/cart/items/{pid}")
    assert r.status_code == 409 and "序號" in r.json()["detail"]


def test_cart_service_refuses_commands_it_does_not_handle(db_session, resident_id):
    ev = NormalizedIoTEvent(device_id=1, sequence_number=0, command=Command.CHECKOUT, product_code=101, weight_grams=1)
    with pytest.raises(ValueError):
        cart_service.apply_event(db_session, resident_id, ev)


def test_packet_guards():
    with pytest.raises(ValueError):
        compute_check_code(b"\x00" * 12, b"k")
    with pytest.raises(PacketDecodeError):
        parse_fields(b"\x00" * 15)
    with pytest.raises(PacketDecodeError):
        decode_packet("not bytes", b"k")  # type: ignore[arg-type]


# ------------------------------------------------------------------ assistant edge cases
@pytest.fixture()
def ai(client):
    app.dependency_overrides[get_provider_selection] = lambda: ProviderSelection(MockProvider())
    return client


def test_assistant_says_so_when_nothing_is_in_stock(ai, resident_id, db_session):
    db_session.query(Product).update({"stock_grams": 0})
    db_session.commit()
    d = ai.post(f"/api/v1/residents/{resident_id}/nutrition/recommendations",
                json={"question": "請推薦適合我的低鈉食材"}).json()
    assert d["recommended_products"] == [] and "目前沒有符合條件且有庫存的商品" in d["answer"]
    assert d["sources"]                                   # general knowledge is still cited


def test_high_sodium_product_is_flagged_for_a_low_sodium_resident(ai, resident_id):
    d = ai.post(f"/api/v1/residents/{resident_id}/nutrition/recommendations",
                json={"question": "菠菜適合我嗎"}).json()
    assert "菠菜" in d["answer"] and "相對較高" in d["answer"]


def test_default_http_client_path_of_the_real_provider(monkeypatch):
    seen = {}

    def handler(req):
        seen["key"] = req.headers["x-api-key"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    real_client = httpx.Client
    monkeypatch.setattr("app.ai.providers.httpx.Client",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    assert AnthropicProvider("sk-x", "m", 3).generate(LLMRequest("s", "u", None)) == "ok"
    assert seen["key"] == "sk-x"


# ------------------------------------------------------------------ operational code
def test_simulator_cli_prints_the_documented_golden_packet():
    out = subprocess.run(
        [sys.executable, "-m", "app.simulator", "--device", "1", "--seq", "1", "--command", "ADD_ITEM",
         "--product", "101", "--weight", "320"], cwd=BACKEND, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0 and GOLDEN in out.stdout and "16 bytes" in out.stdout


@pytest.mark.parametrize("args", [["--seq", "70000"], ["--weight", "99999999"], ["--command", "NOPE"]])
def test_simulator_cli_rejects_bad_values_with_a_message_not_a_traceback(args):
    base = ["--device", "1", "--seq", "1", "--command", "ADD_ITEM", "--product", "101", "--weight", "320"]
    for i in range(0, len(args), 2):
        base[base.index(args[i]) + 1] = args[i + 1]
    out = subprocess.run([sys.executable, "-m", "app.simulator", *base], cwd=BACKEND,
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 2 and "Traceback" not in out.stderr and "error" in out.stderr.lower()


def sqlite_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_seed_entry_point(monkeypatch, capsys):
    from app import seed
    engine, factory = sqlite_factory()
    monkeypatch.setattr(seed, "get_session_factory", lambda: factory)
    seed.main()
    assert "'products': 8" in capsys.readouterr().out
    seed.main()
    assert "'products': 0" in capsys.readouterr().out           # idempotent


def test_check_database_reports_both_outcomes(monkeypatch):
    engine, _ = sqlite_factory()
    monkeypatch.setattr(database, "get_engine", lambda: engine)
    assert database.check_database() is True

    def down():
        raise ConnectionError("db is down")

    monkeypatch.setattr(database, "get_engine", down)
    assert database.check_database() is False                    # never raises, never leaks details


def test_get_db_always_closes_its_session(monkeypatch):
    closed = []

    class FakeSession:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(database, "get_session_factory", lambda: (lambda: FakeSession()))
    gen = database.get_db()
    next(gen)
    gen.close()
    assert closed == [True]
    gen = database.get_db()
    next(gen)
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("request failed"))
    assert closed == [True, True]


def test_sqlite_engine_has_no_postgres_only_connect_args(monkeypatch):
    database.get_engine.cache_clear()
    monkeypatch.setattr(database, "get_settings", lambda: Settings(_env_file=None, database_url="sqlite://"))
    try:
        assert database.get_engine().dialect.name == "sqlite"
    finally:
        database.get_engine.cache_clear()


def test_custom_knowledge_base_path_setting():
    assert Settings(_env_file=None, knowledge_base_path="/x/kb.json").knowledge_base_file == Path("/x/kb.json")
    assert Settings(_env_file=None).knowledge_base_file.name == "nutrition_seed.json"


# ------------------------------------------------------------------ CORS
def test_cors_does_not_allow_unknown_origins(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
