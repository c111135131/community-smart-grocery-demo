import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError, NUTRITION_TIMEOUT_MS, REQUEST_TIMEOUT_MS, askNutritionAssistant, fetchProducts,
  loginWithCard, removeCartItem, sendRawPacket,
} from "../api/client";
import { installFakeApi } from "./fakeApi";
import { EVENT_REPLAY, NUTRITION } from "./fixtures";

const fails = async (p: Promise<unknown>) => {
  try {
    await p;
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError);
    return e as ApiError;
  }
  throw new Error("expected the request to fail");
};

describe("error messages", () => {
  it("shows the backend's own message for client errors", async () => {
    installFakeApi({ "POST /api/v1/residents/login": { status: 401, body: { detail: "找不到此識別卡，請確認卡號" } } });
    const e = await fails(loginWithCard("X"));
    expect(e.status).toBe(401);
    expect(e.message).toBe("找不到此識別卡，請確認卡號");
  });

  it("never shows raw server internals for 5xx", async () => {
    installFakeApi({ "GET /api/v1/products": { status: 500, body: { detail: "Traceback: secret stack info" } } });
    const e = await fails(fetchProducts());
    expect(e.message).toBe("伺服器發生錯誤（HTTP 500），請稍後再試");
    expect(e.message).not.toContain("Traceback");
  });

  it("handles a 5xx that is not JSON (e.g. a proxy error page)", async () => {
    installFakeApi({ "GET /api/v1/products": { status: 502, text: "<html>Bad gateway</html>" } });
    expect((await fails(fetchProducts())).message).toContain("HTTP 502");
  });

  it("explains validation errors without dumping the payload", async () => {
    installFakeApi({ "POST /api/v1/residents/login": { status: 422, body: { detail: [{ loc: ["body"], msg: "x" }] } } });
    expect((await fails(loginWithCard("X"))).message).toBe("輸入格式不正確，請檢查後再試");
  });

  it("reports a malformed success response", async () => {
    installFakeApi({ "GET /api/v1/products": { text: "not json at all" } });
    expect((await fails(fetchProducts())).message).toBe("後端回應的格式不正確");
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const e = await fails(fetchProducts());
    expect(e.status).toBe(0);
    expect(e.message).toContain("無法連線到後端");
  });
});

describe("timeouts", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("gives up on a hanging request after the default timeout", async () => {
    installFakeApi({ "GET /api/v1/products": () => new Promise(() => {}) });
    const result = fails(fetchProducts());
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS - 1);
    let settled = false;
    void result.then(() => (settled = true));
    await Promise.resolve();
    expect(settled).toBe(false);                 // not yet
    await vi.advanceTimersByTimeAsync(2);
    expect((await result).message).toBe("請求逾時，請稍後再試");
  });

  it("gives the nutrition assistant a longer timeout", async () => {
    installFakeApi({ "POST /api/v1/residents/1/nutrition/recommendations": () => new Promise(() => {}) });
    const result = fails(askNutritionAssistant(1, "q"));
    let settled = false;
    void result.then(() => (settled = true));
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 1000);
    expect(settled).toBe(false);                 // still waiting after the default timeout
    await vi.advanceTimersByTimeAsync(NUTRITION_TIMEOUT_MS);
    expect((await result).message).toBe("請求逾時，請稍後再試");
  });

  it("does not time out a request that answers in time", async () => {
    installFakeApi({ "POST /api/v1/residents/1/nutrition/recommendations": { body: NUTRITION } });
    expect((await askNutritionAssistant(1, "q")).provider).toBe("mock");
    expect(vi.getTimerCount()).toBe(0);          // the timeout timer was cleaned up
  });
});

describe("rejected-but-informative responses", () => {
  it("returns the result body for 409 packet rejections", async () => {
    installFakeApi({ "POST /api/v1/residents/1/cart/packets": { status: 409, body: EVENT_REPLAY } });
    const r = await sendRawPacket(1, "AA55");
    expect(r.accepted).toBe(false);
    expect(r.rejection_code).toBe("SEQUENCE_REPLAY");
  });

  it("treats a plain error body (no result) as an error", async () => {
    installFakeApi({ "POST /api/v1/residents/1/cart/packets": { status: 404, body: { detail: "找不到此居民" } } });
    expect((await fails(sendRawPacket(1, "AA55"))).message).toBe("找不到此居民");
  });

  it("DELETE returns its result even when rejected", async () => {
    installFakeApi({ "DELETE /api/v1/residents/1/cart/items/1": { status: 409, body: { accepted: false, events: [], cart: {} } } });
    expect((await removeCartItem(1, 1)).accepted).toBe(false);
  });
});
