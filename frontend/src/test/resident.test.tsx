import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { installFakeApi } from "./fakeApi";
import {
  CART_ONE, CHECKOUT_FAILED, CHECKOUT_PAID, EVENT_FORGED, EVENT_OK, EVENT_REPLAY, NUTRITION,
  healthyRoutes, PACKET_HEX,
} from "./fixtures";
import { openApp, rowIn } from "./helpers";

const P = "/api/v1/products";
const CART = "/api/v1/residents/1/cart";

// ------------------------------------------------------------------ loading + retry
it("shows loading indicators while data is on its way, then the content", async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  installFakeApi({ ...healthyRoutes(), [`GET ${P}`]: async () => (await gate, { body: (await import("./fixtures")).PRODUCTS }) });
  await openApp(userEvent.setup());
  expect(screen.getAllByText("載入中…").length).toBeGreaterThan(0);
  expect(document.querySelector(".spinner")).toBeTruthy();
  release();
  expect(await screen.findByRole("group", { name: "可購買的生鮮商品" })).toBeTruthy();
  await waitFor(() => expect(screen.queryByText("載入中…")).toBeNull());
});

it("lets the user retry a failed product load", async () => {
  const api = installFakeApi({ ...healthyRoutes(), [`GET ${P}`]: { status: 500, body: {} } });
  await openApp(userEvent.setup());
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("伺服器發生錯誤");
  api.set(`GET ${P}`, healthyRoutes()[`GET ${P}`]);                      // backend recovers
  await userEvent.setup().click(within(alert).getByRole("button", { name: "重試" }));
  expect(await screen.findByRole("group", { name: "可購買的生鮮商品" })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(api.count("GET", P)).toBe(2);
});

it("shows an error with retry when the cart cannot be loaded", async () => {
  installFakeApi({ ...healthyRoutes(), [`GET ${CART}`]: { status: 503, body: {} } });
  await openApp(userEvent.setup());
  expect((await screen.findByRole("alert")).textContent).toContain("HTTP 503");
  expect(screen.getByRole("button", { name: "重試" })).toBeTruthy();
});

// ------------------------------------------------------------------ packet simulator
it("shows an accepted packet: hex, field table and all 9 checks passed", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${CART}/events`]: { body: EVENT_OK } });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByRole("button", { name: "加入購物籃" }));
  expect(await screen.findByText(/已加入番茄/)).toBeTruthy();
  const technicalDetails = screen.getByText("IoT 技術展示").closest("details")!;
  expect(technicalDetails.open).toBe(false);
  await user.click(screen.getByText("IoT 技術展示"));
  expect(screen.getByText(/封包已接受，購物車已更新/)).toBeTruthy();
  expect(screen.getByLabelText("封包十六進位內容").textContent).toBe(PACKET_HEX);
  expect(screen.getAllByText(/✓ 通過/)).toHaveLength(9);
  expect(screen.getByText(/SIMULATED/)).toBeTruthy();
  expect(within(screen.getByRole("list", { name: "購物籃內容" })).getByText("NT$ 19.20")).toBeTruthy();
});

it("shows why a replayed packet was rejected, with later steps marked not-run", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${CART}/events`]: { status: 409, body: EVENT_REPLAY } });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByRole("button", { name: "加入購物籃" }));
  expect((await screen.findByRole("alert")).textContent).toContain("序號重複或過舊");
  await user.click(screen.getByText("IoT 技術展示"));
  expect(screen.getByText(/封包被拒絕，購物車未變更/)).toBeTruthy();
  expect(screen.getAllByText(/✗ 失敗/)).toHaveLength(1);
  expect(screen.getAllByText(/— 未執行/)).toHaveLength(2);
});

it("sends a replayed and a tampered packet from the demo buttons", async () => {
  const api = installFakeApi({ ...healthyRoutes(), [`POST ${CART}/events`]: { body: EVENT_OK },
    [`POST ${CART}/packets`]: (req) => ({
      status: 400, body: (req.body as { packet_hex: string }).packet_hex === PACKET_HEX ? EVENT_REPLAY : EVENT_FORGED }) });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByRole("button", { name: "加入購物籃" }));
  await screen.findByText(/已加入番茄/);
  await user.click(screen.getByText("IoT 技術展示"));
  await user.click(screen.getByText("進階：重放與竄改封包演示"));
  await user.click(screen.getByRole("button", { name: "重送相同封包（重放）" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("序號重複或過舊"));
  await user.click(screen.getByRole("button", { name: "竄改重量後送出" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("檢查碼不符"));
  const sent = api.calls.filter((c) => c.path.endsWith("/packets")).map((c) => (c.body as { packet_hex: string }).packet_hex);
  expect(sent[0]).toBe(PACKET_HEX);
  expect(sent[1]).not.toBe(PACKET_HEX);
  expect(sent[1]).toHaveLength(32);
});

it("rejects a non-numeric weight before calling the backend", async () => {
  const api = installFakeApi({ ...healthyRoutes(), [`POST ${CART}/events`]: { body: EVENT_OK } });
  const user = userEvent.setup();
  await openApp(user);
  await user.clear(screen.getByLabelText("重量（公克）"));
  await user.type(screen.getByLabelText("重量（公克）"), "abc");
  await user.click(screen.getByRole("button", { name: "加入購物籃" }));
  expect((await screen.findByRole("alert")).textContent).toContain("重量必須是 0 以上的整數");
  expect(api.count("POST", `${CART}/events`)).toBe(0);
});

it("shows a readable error when sending a packet fails", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${CART}/events`]: { status: 404, body: { detail: "找不到此裝置" } } });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByRole("button", { name: "加入購物籃" }));
  expect((await screen.findByRole("alert")).textContent).toBe("找不到此裝置");
});

// ------------------------------------------------------------------ cart + checkout
const withCart = (extra = {}) => ({ ...healthyRoutes(), [`GET ${CART}`]: { body: CART_ONE }, ...extra });

it("shows backend-calculated prices and removes a line through the gateway", async () => {
  installFakeApi(withCart({ "DELETE /api/v1/residents/1/cart/items/1": { body: {
    accepted: true, events: [{ ...EVENT_OK, packet_hex: PACKET_HEX }], cart: (await import("./fixtures")).CART_EMPTY } } }));
  const user = userEvent.setup();
  await openApp(user);
  const row = within(await screen.findByRole("list", { name: "購物籃內容" })).getByRole("listitem");
  expect(row.textContent).toContain("NT$ 60.00");
  expect(row.textContent).toContain("NT$ 19.20");
  await user.click(screen.getByRole("button", { name: "移除 番茄" }));
  expect(await screen.findByText("已從購物籃移除商品。")).toBeTruthy();
  expect(await screen.findByText(/購物籃是空的/)).toBeTruthy();
});

it("shows the reason when a removal is rejected, and keeps the cart", async () => {
  installFakeApi(withCart({ "DELETE /api/v1/residents/1/cart/items/1": { status: 409, body: {
    accepted: false, events: [EVENT_REPLAY], cart: CART_ONE } } }));
  const user = userEvent.setup();
  await openApp(user);
  await user.click(await screen.findByRole("button", { name: "移除 番茄" }));
  expect((await screen.findByRole("alert")).textContent).toContain("移除被拒絕");
  expect(screen.getByRole("list", { name: "購物籃內容" })).toBeTruthy();
});

it("cannot check out an empty cart", async () => {
  installFakeApi(healthyRoutes());
  await openApp(userEvent.setup());
  expect((screen.getByRole("button", { name: "結帳" }) as HTMLButtonElement).disabled).toBe(true);
});

it("a failed payment keeps the cart and is clearly labelled", async () => {
  const api = installFakeApi(withCart({ [`POST ${"/api/v1/residents/1/checkout"}`]: { body: CHECKOUT_FAILED } }));
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByText("付款測試設定"));
  await user.click(await screen.findByLabelText("付款失敗"));
  await user.click(screen.getByRole("button", { name: /^結帳/ }));
  expect(await screen.findByText(/付款失敗（訂單 #6/)).toBeTruthy();
  expect(screen.getByRole("list", { name: "購物籃內容" })).toBeTruthy();              // cart kept
  expect(api.count("GET", P)).toBe(1);                                                  // stock not reloaded
  expect(api.calls.find((c) => c.path.endsWith("/checkout"))?.body).toEqual({ payment_simulation: "FAILURE" });
});

it("a paid order shows the receipt, empties the cart and refreshes stock", async () => {
  const api = installFakeApi(withCart({ "POST /api/v1/residents/1/checkout": { body: CHECKOUT_PAID } }));
  const user = userEvent.setup();
  await openApp(user);
  await user.click(await screen.findByRole("button", { name: /^結帳/ }));
  expect(await screen.findByText(/付款成功，訂單 #7/)).toBeTruthy();
  expect(within(screen.getByRole("table", { name: "結帳明細" })).getByText("NT$ 19.20", { selector: ".total" })).toBeTruthy();
  expect(await screen.findByText(/購物籃是空的/)).toBeTruthy();
  await waitFor(() => expect(api.count("GET", P)).toBe(2));                             // products reloaded
});

it("explains a refused checkout (409), e.g. insufficient stock", async () => {
  installFakeApi(withCart({ "POST /api/v1/residents/1/checkout": { status: 409, body: { detail: "番茄 庫存不足（購物車 320 公克，庫存 100 公克）" } } }));
  const user = userEvent.setup();
  await openApp(user);
  await user.click(await screen.findByRole("button", { name: /^結帳/ }));
  expect((await screen.findByRole("alert")).textContent).toContain("庫存不足");
  expect(screen.getByRole("list", { name: "購物籃內容" })).toBeTruthy();
});

it("prevents a double submit while checkout is in flight", async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const api = installFakeApi(withCart({ "POST /api/v1/residents/1/checkout": async () => (await gate, { body: CHECKOUT_PAID }) }));
  const user = userEvent.setup();
  await openApp(user);
  await user.click(await screen.findByRole("button", { name: /^結帳/ }));
  const busy = screen.getByRole("button", { name: "結帳中…" }) as HTMLButtonElement;
  expect(busy.disabled).toBe(true);
  await user.click(busy);
  release();
  await screen.findByText(/付款成功，訂單 #7/);
  expect(api.count("POST", "/api/v1/residents/1/checkout")).toBe(1);
});

// ------------------------------------------------------------------ nutrition assistant
const ASK = "/api/v1/residents/1/nutrition/recommendations";

it("shows the answer with provider, recommended products, sources and tool calls", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${ASK}`]: { body: NUTRITION } });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByText("提問範例"));
  await user.click(screen.getByRole("button", { name: "請推薦適合我的低鈉食材" }));
  await user.click(screen.getByRole("button", { name: "詢問助理" }));
  const citation = await screen.findByRole("link", { name: "參考來源 1" });
  const panel = citation.closest("section")!;
  expect(citation.textContent).toBe("[1]");
  expect(panel.querySelector(".answer")!.textContent).not.toContain("[nutrition_seed_013]");
  await user.click(citation);
  expect(document.getElementById("nutrition-source-0")?.hasAttribute("open")).toBe(true);
  await user.click(within(panel).getByText("回答與資料使用資訊"));
  expect(within(panel).getByText(/Mock（本地範本，未呼叫外部 LLM）/)).toBeTruthy();
  expect(within(panel).getByText(/助理使用的唯讀工具（1 次呼叫）/)).toBeTruthy();
  expect(within(panel).getByText("香蕉")).toBeTruthy();
});

it("labels guardrail refusals and says when no sources were used", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${ASK}`]: { body: { ...NUTRITION, provider: "guardrail",
    answer: "我只能提供一般飲食資訊，無法執行結帳", sources: [], source_details: [], recommended_products: [], tool_calls: [] } } });
  const user = userEvent.setup();
  await openApp(user);
  await user.type(screen.getByLabelText("您的問題"), "幫我結帳");
  await user.click(screen.getByRole("button", { name: "詢問助理" }));
  expect(await screen.findByText(/護欄（未呼叫任何模型）/)).toBeTruthy();
  expect(screen.getByText(/沒有引用知識庫片段/)).toBeTruthy();
});

it("requests a basket recommendation and shows the basket used", async () => {
  const api = installFakeApi({ ...healthyRoutes(), [`POST ${ASK}`]: {
    body: { ...NUTRITION, provider: "gemini",
      basket_items: [{ product_code: 101, name: "番茄", weight_grams: 300 }] },
  } });
  const user = userEvent.setup();
  await openApp(user);
  await user.click(screen.getByRole("button", { name: "購物籃推薦" }));
  expect(await screen.findByText(/本次使用的購物籃：番茄 300 公克/)).toBeTruthy();
  expect(screen.getByRole("heading", { name: "推薦補買商品" })).toBeTruthy();
  expect(api.count("POST", ASK)).toBe(1);
});

it("shows the fallback notice and the privacy note for an external LLM", async () => {
  installFakeApi({ ...healthyRoutes(), [`POST ${ASK}`]: { body: { ...NUTRITION, provider: "anthropic" } } });
  const user = userEvent.setup();
  await openApp(user);
  await user.type(screen.getByLabelText("您的問題"), "低鈉");
  await user.click(screen.getByRole("button", { name: "詢問助理" }));
  expect(await screen.findByText(/Anthropic（外部 LLM）/)).toBeTruthy();
  expect(screen.getByText(/不含姓名、卡號、價格與庫存數量/)).toBeTruthy();
});

it("shows an error when the assistant fails and lets the user ask again", async () => {
  const api = installFakeApi({ ...healthyRoutes(), [`POST ${ASK}`]: { status: 500, body: {} } });
  const user = userEvent.setup();
  await openApp(user);
  await user.type(screen.getByLabelText("您的問題"), "低鈉");
  await user.click(screen.getByRole("button", { name: "詢問助理" }));
  expect((await screen.findByRole("alert")).textContent).toContain("伺服器發生錯誤");
  api.set(`POST ${ASK}`, { body: NUTRITION });
  await user.click(screen.getByRole("button", { name: "詢問助理" }));
  expect(await screen.findByText(/Mock（本地範本/)).toBeTruthy();
  expect(screen.queryByText(/伺服器發生錯誤/)).toBeNull();
});

it("does not allow an empty question", async () => {
  installFakeApi(healthyRoutes());
  await openApp(userEvent.setup());
  expect((screen.getByRole("button", { name: "詢問助理" }) as HTMLButtonElement).disabled).toBe(true);
});

void rowIn;
