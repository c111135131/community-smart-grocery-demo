"""Runs scripts/demo_smoke.py (the same script users run against a live stack) in-process."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import demo_smoke  # noqa: E402


@pytest.fixture()
def http(client, monkeypatch):
    # /health pings the REAL database engine; everything else here uses in-memory SQLite.
    # Pin it so this test never depends on whether PostgreSQL happens to be running.
    monkeypatch.setattr("app.api.health.check_database", lambda: True)

    def call(method, path, body=None):
        r = client.request(method, path, json=body)
        return r.status_code, r.json()

    return call


def sections(lines):
    return [m.group(1) for l in lines if (m := re.match(r"^\n?(\d+)\. ", l))]


def test_full_demo_flow_passes(http):
    lines = []
    result = demo_smoke.run_demo(http, lines.append)
    assert sections(lines) == [str(i) for i in range(1, 12)]     # no section was skipped
    assert result["steps"] == sum(1 for l in lines if l.startswith("  [ OK ]"))
    assert result["steps"] >= 40
    assert result["paid_order"] > result["failed_order"]
    assert not any("[FAIL]" in line for line in lines)


def test_demo_is_repeatable_against_existing_data(http):
    demo_smoke.run_demo(http, lambda _: None)
    assert demo_smoke.run_demo(http, lambda _: None)["steps"] >= 40   # second run, dirty state


def test_demo_works_for_the_other_seeded_card(http):
    assert demo_smoke.run_demo(http, lambda _: None, card_id="CARD-1002")["steps"] >= 40


def test_demo_reports_a_clear_failure_when_the_system_misbehaves(client, http):
    def broken(method, path, body=None):
        status, data = http(method, path, body)
        if path.endswith("/checkout") and body == {"payment_simulation": "SUCCESS"} and status == 200:
            data["payment_status"] = "FAILED"      # pretend the backend got it wrong
        return status, data

    with pytest.raises(demo_smoke.DemoFailure, match="PAID"):
        demo_smoke.run_demo(broken, lambda _: None)


def test_unreachable_backend_gives_actionable_message():
    with pytest.raises(demo_smoke.DemoFailure, match="Is the backend running"):
        demo_smoke.urllib_http("http://127.0.0.1:9", timeout=2)("GET", "/health", None)


def test_helpers():
    assert str(demo_smoke.expected_subtotal("45.00", 333)) == "14.99"         # half-up, not banker's
    assert demo_smoke.tamper("AA550001000102006500014000D9847C") == "AA550001000102006500014100D9847C"


def test_demo_fails_clearly_when_the_database_is_down(client, monkeypatch):
    monkeypatch.setattr("app.api.health.check_database", lambda: False)

    def call(method, path, body=None):
        r = client.request(method, path, json=body)
        return r.status_code, r.json()

    with pytest.raises(demo_smoke.DemoFailure, match="PostgreSQL is connected"):
        demo_smoke.run_demo(call, lambda _: None)
