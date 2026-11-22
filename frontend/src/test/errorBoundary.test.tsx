import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import ErrorBoundary from "../components/ErrorBoundary";

function Bomb(): never {
  throw new Error("render crash");
}

it("shows a recoverable message instead of a blank page", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  const reload = vi.fn();
  vi.stubGlobal("location", { ...window.location, reload });
  render(<ErrorBoundary><Bomb /></ErrorBoundary>);
  expect(screen.getByRole("alert").textContent).toContain("畫面發生未預期的錯誤");
  await userEvent.setup().click(screen.getByRole("button", { name: "重新整理頁面" }));
  expect(reload).toHaveBeenCalled();
});

it("renders children normally when nothing fails", () => {
  render(<ErrorBoundary><p>fine</p></ErrorBoundary>);
  expect(screen.getByText("fine")).toBeTruthy();
});
