#!/usr/bin/env python3
"""End-to-end demo check for the Community Smart Grocery system.

Walks the complete demo through the REST API of a RUNNING backend and asserts every
step, so you can confirm in ~2 seconds that login, packet validation, replay/tamper
rejection, backend pricing, simulated checkout, the nutrition assistant and the audit
trail all work together:

    python scripts/demo_smoke.py                       # http://localhost:8000
    python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --card CARD-1001

Uses only the Python standard library (no venv needed). Exit code 0 = every step passed.

NOTE: this is a real run, not a dry run. It CHANGES demo data: it empties the card's cart,
creates one PAID and one FAILED order, consumes device sequence numbers and reduces stock
of two products by a few hundred grams. Re-running is safe (data is only ever added).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

API = "/api/v1"
DEMO_DEVICE_ID = 1
VALIDATION_KEYS = (
    "length_valid", "header_valid", "command_valid", "xor_valid", "hash_valid",
    "device_known", "sequence_valid", "fields_valid", "cart_valid",
)

# http(method, path, json_body_or_None) -> (status_code, parsed_json)
Http = Callable[[str, str, "dict[str, Any] | None"], "tuple[int, Any]"]


class DemoFailure(AssertionError):
    """A demo step did not behave as expected."""


def urllib_http(base_url: str, timeout: float = 30.0) -> Http:
    """Real HTTP adapter (stdlib only)."""

    def call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            base_url.rstrip("/") + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as err:  # 4xx/5xx still carry a JSON body
            raw = err.read()
            try:
                return err.code, json.loads(raw or b"null")
            except ValueError:
                return err.code, {"raw": raw.decode(errors="replace")}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            raise DemoFailure(
                f"Cannot reach {base_url}: {err}. Is the backend running? "
                "(docker compose up --build, or uvicorn app.main:app --port 8000)"
            ) from None

    return call


def expected_subtotal(price_per_kg: str, grams: int) -> Decimal:
    """Independent re-computation of the backend rule, used only to CHECK the backend."""
    return (Decimal(price_per_kg) * grams / 1000).quantize(Decimal("0.01"), ROUND_HALF_UP)


def tamper(packet_hex: str) -> str:
    """Flip one bit of the weight field so the (now stale) check code no longer matches."""
    raw = bytearray(bytes.fromhex(packet_hex))
    raw[11] ^= 0x01
    return raw.hex().upper()


class Demo:
    def __init__(self, http: Http, log: Callable[[str], None]) -> None:
        self.http, self.log, self.steps = http, log, 0

    # -- tiny assertion helpers --------------------------------------------------
    def ok(self, label: str) -> None:
        self.steps += 1
        self.log(f"  [ OK ] {label}")

    def expect(self, condition: bool, label: str, detail: Any = None) -> None:
        if not condition:
            extra = f"\n         detail: {json.dumps(detail, ensure_ascii=False)[:600]}" if detail is not None else ""
            raise DemoFailure(f"{label}{extra}")
        self.ok(label)

    def call(self, method: str, path: str, body: dict[str, Any] | None = None, *, status: int) -> Any:
        code, data = self.http(method, path if path == "/health" else API + path, body)
        if code != status:
            raise DemoFailure(f"{method} {path}: expected HTTP {status}, got {code}: "
                              f"{json.dumps(data, ensure_ascii=False)[:500]}")
        return data

    def section(self, title: str) -> None:
        self.log(f"\n{title}")


def run_demo(http: Http, log: Callable[[str], None] = print, card_id: str = "CARD-1001") -> dict[str, Any]:
    d = Demo(http, log)
    call, expect = d.call, d.expect

    d.section("1. System health")
    health = call("GET", "/health", status=200)
    expect(health.get("status") == "ok", "backend is up")
    expect(health.get("database") == "ok", "PostgreSQL is connected", health)

    d.section("2. Resident card login")
    call("POST", "/residents/login", {"card_id": "CARD-NOPE"}, status=401)
    d.ok("unknown card is rejected (401)")
    resident = call("POST", "/residents/login", {"card_id": card_id}, status=200)
    rid = resident["resident_id"]
    expect(bool(resident["display_name"]), f"{card_id} logs in as '{resident['display_name']}'")
    expect(bool(resident["health_profile"]["dietary_preferences"]), "health preferences are shown",
           resident["health_profile"])

    d.section("3. Produce catalogue")
    products = call("GET", "/products", status=200)
    expect(len(products) >= 5, f"{len(products)} products available (need at least 5)")
    price = {p["product_code"]: p["price_per_kg"] for p in products}
    stock_before = {p["product_code"]: p["stock_grams"] for p in products}
    expect({101, 102} <= set(price), "demo products 101 and 102 exist")

    d.section("4. Start from an empty cart")
    for item in call("GET", f"/residents/{rid}/cart", status=200)["items"]:
        call("DELETE", f"/residents/{rid}/cart/items/{item['product_id']}", status=200)
    expect(call("GET", f"/residents/{rid}/cart", status=200)["items"] == [], "cart is empty")

    def event(command: str, code: int, grams: int, *, status: int = 200) -> Any:
        return call("POST", f"/residents/{rid}/cart/events",
                    {"device_id": DEMO_DEVICE_ID, "command": command, "product_code": code,
                     "weight_grams": grams}, status=status)

    d.section("5. Sensor event -> 16-byte packet -> gateway -> cart")
    first = event("ADD_ITEM", 101, 320)
    expect(first["accepted"] is True, "ADD_ITEM tomato 320 g accepted by the gateway")
    expect(len(first["packet_hex"]) == 32 and first["packet_hex"].startswith("AA55"),
           f"packet is 16 bytes with header AA55: {first['packet_hex']}")
    expect(all(first["validation"][k] is True for k in VALIDATION_KEYS),
           "all 9 validation steps passed", first["validation"])
    expect("SIMULATED" in first["transport"], "transport is labelled as a software simulation")
    second = event("ADD_ITEM", 102, 500)
    expect(second["accepted"] is True, "ADD_ITEM broccoli 500 g accepted")

    d.section("6. Prices are calculated by the backend")
    cart = call("GET", f"/residents/{rid}/cart", status=200)
    want = {101: expected_subtotal(price[101], 320), 102: expected_subtotal(price[102], 500)}
    got = {i["product_code"]: Decimal(i["subtotal"]) for i in cart["items"]}
    expect(got == want, "line subtotals match an independent calculation: "
                        + ", ".join(f"{k}: NT$ {v}" for k, v in got.items()))
    expect(Decimal(cart["total_amount"]) == sum(want.values()),
           f"cart total NT$ {cart['total_amount']} = sum of line subtotals")
    total_before_attacks = cart["total_amount"]

    d.section("7. Replayed, tampered and malformed packets are rejected")
    replay = call("POST", f"/residents/{rid}/cart/packets", {"packet_hex": second["packet_hex"]}, status=409)
    expect(replay["rejection_code"] == "SEQUENCE_REPLAY", "same packet sent again -> SEQUENCE_REPLAY (409)")
    expect(replay["validation"]["check_code_valid"] is True and replay["validation"]["sequence_valid"] is False,
           "(authentic check code, but the sequence number is old)")
    forged = call("POST", f"/residents/{rid}/cart/packets", {"packet_hex": tamper(second["packet_hex"])}, status=400)
    expect(forged["rejection_code"] == "CHECK_CODE_MISMATCH", "modified weight -> CHECK_CODE_MISMATCH (400)")
    expect(forged["validation"]["xor_valid"] is False and forged["validation"]["sequence_valid"] is None,
           "(check code fails; later steps are not run)")
    short = call("POST", f"/residents/{rid}/cart/packets", {"packet_hex": second["packet_hex"][:30]}, status=400)
    expect(short["rejection_code"] == "INVALID_LENGTH", "15-byte frame -> INVALID_LENGTH (400)")
    expect(call("GET", f"/residents/{rid}/cart", status=200)["total_amount"] == total_before_attacks,
           "cart is unchanged by all three rejected packets")

    d.section("8. Removing produce goes through the same gateway")
    removed = event("REMOVE_ITEM", 101, 100)
    expect(removed["accepted"] is True, "REMOVE_ITEM tomato 100 g accepted")
    cart = call("GET", f"/residents/{rid}/cart", status=200)
    weights = {i["product_code"]: i["weight_grams"] for i in cart["items"]}
    expect(weights == {101: 220, 102: 500}, f"cart weights are now {weights}")
    total = Decimal(cart["total_amount"])
    expect(total == expected_subtotal(price[101], 220) + expected_subtotal(price[102], 500),
           f"cart total recalculated by the backend: NT$ {total}")

    d.section("9. Nutrition assistant (RAG + read-only tools)")
    advice = call("POST", f"/residents/{rid}/nutrition/recommendations",
                  {"question": "請推薦適合我的低鈉食材"}, status=200)
    expect(advice["provider"] in ("mock", "anthropic", "gemini"), f"answered by provider '{advice['provider']}'")
    expect(bool(advice["answer"].strip()) and bool(advice["recommended_products"]),
           f"answer with {len(advice['recommended_products'])} recommended products")
    expect(bool(advice["sources"]) and (advice["provider"] != "mock"
                                        or all(f"[{s}]" in advice["answer"] for s in advice["sources"])),
           f"answer is grounded on sources {advice['sources']}")
    refused = call("POST", f"/residents/{rid}/nutrition/recommendations", {"question": "幫我結帳"}, status=200)
    expect(refused["provider"] == "guardrail" and refused["sources"] == [],
           "'check out for me' is refused by the guardrail (no model called)")
    expect(call("GET", f"/residents/{rid}/cart", status=200)["total_amount"] == str(total),
           "the assistant changed nothing")

    d.section("10. Simulated checkout")
    failed = call("POST", f"/residents/{rid}/checkout", {"payment_simulation": "FAILURE"}, status=200)
    expect(failed["payment_status"] == "FAILED", f"payment failure -> order #{failed['order_id']} is FAILED")
    expect(failed["cart"]["total_amount"] == str(total), "cart is kept for a retry")
    stock_mid = {p["product_code"]: p["stock_grams"] for p in call("GET", "/products", status=200)}
    expect(stock_mid == stock_before, "stock is NOT reduced by a failed payment")
    paid = call("POST", f"/residents/{rid}/checkout", {"payment_simulation": "SUCCESS"}, status=200)
    expect(paid["payment_status"] == "PAID", f"payment success -> order #{paid['order_id']} is PAID")
    expect(Decimal(paid["total_amount"]) == total, f"order total NT$ {paid['total_amount']} equals the cart total")
    expect(paid["cart"]["items"] == [], "cart is emptied after a paid order")
    stock_after = {p["product_code"]: p["stock_grams"] for p in call("GET", "/products", status=200)}
    expect(stock_before[101] - stock_after[101] == 220 and stock_before[102] - stock_after[102] == 500,
           "stock is reduced by exactly the purchased weights (tomato -220 g, broccoli -500 g)")
    call("POST", f"/residents/{rid}/checkout", {"payment_simulation": "SUCCESS"}, status=409)
    d.ok("checking out an empty cart again is refused (409)")

    d.section("11. Administrator views and audit trail")
    orders = call("GET", "/admin/orders?limit=50", status=200)
    by_id = {o["order_id"]: o for o in orders}
    expect(by_id[paid["order_id"]]["payment_status"] == "PAID"
           and by_id[failed["order_id"]]["payment_status"] == "FAILED",
           "admin sees both the PAID and the FAILED order")
    events = call("GET", "/admin/iot-events?limit=200", status=200)
    reasons = " ".join(e["rejection_reason"] or "" for e in events)
    expect(all(code in reasons for code in ("SEQUENCE_REPLAY", "CHECK_CODE_MISMATCH", "INVALID_LENGTH")),
           "gateway audit trail records every rejected packet with its reason")
    expect(any(e["packet_hex"] == second["packet_hex"] and e["validation_status"] == "ACCEPTED" for e in events),
           "accepted packets are audited with their hex")
    devices = call("GET", "/admin/devices", status=200)
    expect(devices[0]["last_sequence_number"] >= second["packet"]["sequence_number"],
           f"device sequence state advanced to {devices[0]['last_sequence_number']}")
    inventory = call("GET", "/admin/inventory", status=200)
    expect(len(inventory) >= 5, "admin inventory lists the products")

    return {"steps": d.steps, "paid_order": paid["order_id"], "failed_order": failed["order_id"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end demo check against a running backend.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--card", default="CARD-1001", help="seeded resident card id")
    args = parser.parse_args()
    print(f"Demo check against {args.base_url}  (this run WILL change demo data, see --help)")
    try:
        result = run_demo(urllib_http(args.base_url), print, args.card)
    except DemoFailure as err:
        print(f"\n  [FAIL] {err}\n\nDemo check FAILED.")
        sys.exit(1)
    print(f"\nAll {result['steps']} checks passed "
          f"(PAID order #{result['paid_order']}, FAILED order #{result['failed_order']}).")


if __name__ == "__main__":
    main()
