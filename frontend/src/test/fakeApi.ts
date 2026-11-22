// A tiny in-memory stand-in for the backend: tests register routes, the app calls fetch().
import { vi } from "vitest";

export interface FakeRequest {
  method: string;
  path: string; // without scheme/host, including any query string
  body: unknown;
}
export interface FakeResponse {
  status?: number;
  body?: unknown;
  text?: string; // raw (non-JSON) body
}
export type Handler = FakeResponse | ((req: FakeRequest) => FakeResponse | Promise<FakeResponse>);

export function installFakeApi(routes: Record<string, Handler> = {}) {
  const table = new Map<string, Handler>(Object.entries(routes));
  const calls: FakeRequest[] = [];
  const unhandled: string[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    const req: FakeRequest = {
      method,
      path,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(req);
    const handler = table.get(`${method} ${path}`) ?? table.get(`${method} ${path.split("?")[0]}`);
    if (!handler) {
      unhandled.push(`${method} ${path}`);
      throw new TypeError("Failed to fetch (no fake route)");
    }
    const work = (async () => (typeof handler === "function" ? await handler(req) : handler))();
    const signal = init?.signal;
    const aborted = new Promise<never>((_, reject) => {
      signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    });
    const res = await Promise.race([work, aborted]);
    return new Response(res.text ?? JSON.stringify(res.body ?? null), {
      status: res.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  return {
    calls,
    unhandled,
    set: (key: string, handler: Handler) => void table.set(key, handler),
    count: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path).length,
  };
}
