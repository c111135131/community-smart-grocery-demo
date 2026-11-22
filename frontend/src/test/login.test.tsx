import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import App from "../App";
import { installFakeApi } from "./fakeApi";
import { healthyRoutes } from "./fixtures";
import { openApp } from "./helpers";

const type = async (user: ReturnType<typeof userEvent.setup>, card: string) => {
  await user.type(await screen.findByLabelText("識別卡號"), card);
  await user.click(screen.getByRole("button", { name: "登入" }));
};

it("logs in and shows the profile with health preferences", async () => {
  const api = installFakeApi(healthyRoutes());
  await openApp(userEvent.setup());
  expect(screen.getByText("低鈉")).toBeTruthy();
  expect(api.calls.find((c) => c.method === "POST" && c.path.endsWith("/login"))?.body).toEqual({ card_id: "CARD-1001" });
  expect(api.unhandled).toEqual([]);
});

it("disables the button until a card id is typed and while logging in", async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  installFakeApi({ ...healthyRoutes(), "POST /api/v1/residents/login": async () => (await gate, { body: {} }) });
  const user = userEvent.setup();
  render(<App />);
  const button = () => screen.getByRole("button", { name: /^登入/ }) as HTMLButtonElement;
  expect(button().disabled).toBe(true);
  await user.type(screen.getByLabelText("識別卡號"), "CARD-1001");
  expect(button().disabled).toBe(false);
  await user.click(button());
  expect(screen.getByRole("button", { name: "登入中…" })).toBeTruthy();      // loading indicator
  expect((screen.getByRole("button", { name: "登入中…" }) as HTMLButtonElement).disabled).toBe(true);
  release();
});

it("shows the backend's message for an unknown card and marks the field invalid", async () => {
  installFakeApi({ ...healthyRoutes(),
    "POST /api/v1/residents/login": { status: 401, body: { detail: "找不到此識別卡，請確認卡號" } } });
  render(<App />);
  await type(userEvent.setup(), "CARD-9999");
  expect((await screen.findByRole("alert")).textContent).toContain("找不到此識別卡");
  expect(screen.getByLabelText("識別卡號").getAttribute("aria-invalid")).toBe("true");
});

it("shows a friendly message when the server fails", async () => {
  installFakeApi({ ...healthyRoutes(), "POST /api/v1/residents/login": { status: 500, body: { detail: "boom" } } });
  render(<App />);
  await type(userEvent.setup(), "CARD-1001");
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("伺服器發生錯誤");
  expect(alert.textContent).not.toContain("boom");
});

it("tells the user when the backend is offline, in the form and in the footer", async () => {
  installFakeApi({});                                       // every request fails to connect
  render(<App />);
  await type(userEvent.setup(), "CARD-1001");
  await waitFor(() => expect(screen.getAllByRole("alert").some((a) => a.textContent?.includes("無法連線到後端"))).toBe(true));
  expect(screen.getByText(/後端離線/).textContent).toContain("docker compose up");
});

it("reports a database outage in the footer while the API is still up", async () => {
  installFakeApi({ ...healthyRoutes(), "GET /health": { body: { status: "ok", service: "b", database: "unavailable" } } });
  render(<App />);
  expect(await screen.findByText(/未連線（請執行 docker compose up -d db）/)).toBeTruthy();
});

it("restores the session after a refresh and drops it if the resident vanished", async () => {
  installFakeApi(healthyRoutes());
  sessionStorage.setItem("csg.residentId", "1");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Demo Resident" })).toBeTruthy();
});

it("falls back to the login form when the saved session is no longer valid", async () => {
  installFakeApi({ ...healthyRoutes(), "GET /api/v1/residents/1": { status: 404, body: { detail: "找不到此居民" } } });
  sessionStorage.setItem("csg.residentId", "1");
  render(<App />);
  expect(await screen.findByLabelText("識別卡號")).toBeTruthy();
  expect(sessionStorage.getItem("csg.residentId")).toBeNull();
});
