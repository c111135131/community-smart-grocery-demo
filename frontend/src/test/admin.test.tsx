import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import App from "../App";
import { installFakeApi } from "./fakeApi";
import { healthyRoutes } from "./fixtures";

const openAdmin = async (user: ReturnType<typeof userEvent.setup>) => {
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "管理" }));
};

it("shows inventory, recent orders (PAID and FAILED) and the gateway audit trail", async () => {
  const api = installFakeApi(healthyRoutes());
  await openAdmin(userEvent.setup());
  const orders = await screen.findByRole("table", { name: "最近訂單" });
  expect(within(orders).getByText(/已付款/)).toBeTruthy();
  expect(within(orders).getByText(/付款失敗/)).toBeTruthy();
  const audit = await screen.findByRole("table", { name: "IoT 事件稽核紀錄" });
  expect(within(audit).getByText("✓ 接受")).toBeTruthy();
  expect(within(audit).getByText("✗ 拒絕")).toBeTruthy();
  expect(within(audit).getAllByText("AA550001000002006500012C00B4160B")).toHaveLength(2);
  expect(screen.getByText(/最後接受序號/).textContent).toContain("0");
  expect(await screen.findByRole("table", { name: "商品庫存清單" })).toBeTruthy();
  expect(api.unhandled).toEqual([]);
});

it("shows an empty state when there are no orders or events yet", async () => {
  installFakeApi({ ...healthyRoutes(), "GET /api/v1/admin/orders": { body: [] }, "GET /api/v1/admin/iot-events": { body: [] } });
  await openAdmin(userEvent.setup());
  expect(await screen.findByText("尚無訂單。")).toBeTruthy();
  expect(await screen.findByText(/尚無事件/)).toBeTruthy();
});

it("each admin panel fails independently and offers a retry", async () => {
  const api = installFakeApi({ ...healthyRoutes(), "GET /api/v1/admin/orders": { status: 500, body: {} } });
  const user = userEvent.setup();
  await openAdmin(user);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("伺服器發生錯誤");
  expect(await screen.findByRole("table", { name: "商品庫存清單" })).toBeTruthy();    // others still work
  expect(await screen.findByRole("table", { name: "IoT 事件稽核紀錄" })).toBeTruthy();
  api.set("GET /api/v1/admin/orders", healthyRoutes()["GET /api/v1/admin/orders"]);
  await user.click(within(alert).getByRole("button", { name: "重試" }));
  expect(await screen.findByRole("table", { name: "最近訂單" })).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("the refresh buttons reload fresh data", async () => {
  const api = installFakeApi(healthyRoutes());
  const user = userEvent.setup();
  await openAdmin(user);
  await screen.findByRole("table", { name: "最近訂單" });
  const before = api.count("GET", "/api/v1/admin/orders?limit=20");
  const orderPanel = screen.getByRole("heading", { name: "最近訂單（管理）" }).closest("section")!;
  await user.click(within(orderPanel).getByRole("button", { name: "重新整理" }));
  await waitFor(() => expect(api.count("GET", "/api/v1/admin/orders?limit=20")).toBe(before + 1));
});
