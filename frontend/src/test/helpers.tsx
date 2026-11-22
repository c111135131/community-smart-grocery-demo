import { render, screen, within } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";
import App from "../App";

export type User = ReturnType<typeof userEvent.setup>;

export async function openApp(user: User, card = "CARD-1001") {
  render(<App />);
  await user.type(await screen.findByLabelText("識別卡號"), card);
  await user.click(screen.getByRole("button", { name: "登入" }));
  await screen.findByRole("heading", { name: "Demo Resident" });
}

/** Row of a table (found by its accessible caption) whose text matches. */
export const rowIn = (caption: string, text: RegExp) =>
  within(screen.getByRole("table", { name: caption })).getByRole("row", { name: text });
