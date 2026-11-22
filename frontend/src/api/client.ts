// Thin HTTP REST client. All business data comes from the backend (no trusted logic here).
import type {
  AdminOrder,
  Cart,
  CartEventResult,
  CheckoutResult,
  CommandName,
  Device,
  HealthResponse,
  IotEvent,
  NutritionResponse,
  PaymentSimulation,
  Product,
  RemoveItemResult,
  Resident,
} from "./types";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Error carrying the HTTP status and a user-readable message. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Default per-request timeout. The nutrition assistant gets longer (an LLM may be involved). */
export const REQUEST_TIMEOUT_MS = 15_000;
export const NUTRITION_TIMEOUT_MS = 30_000;

/** fetch() with a timeout; network and timeout failures become readable ApiErrors. */
async function fetchWithTimeout(
  url: string,
  init: RequestInit | undefined,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch {
    if (controller.signal.aborted) throw new ApiError(0, "請求逾時，請稍後再試");
    throw new ApiError(0, "無法連線到後端，請確認後端已啟動");
  } finally {
    clearTimeout(timer);
  }
}

/** Turn an error response into a message for the user (never shows raw server internals). */
function describeFailure(status: number, body: unknown): string {
  if (status >= 500) return `伺服器發生錯誤（HTTP ${status}），請稍後再試`;
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  if (status === 422) return "輸入格式不正確，請檢查後再試";
  return `後端回應 HTTP ${status}`;
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, init, timeoutMs);
  const body = await readJson(res);
  if (!res.ok) throw new ApiError(res.status, describeFailure(res.status, body));
  if (body === undefined) throw new ApiError(res.status, "後端回應的格式不正確");
  return body as T;
}

export const fetchHealth = () => request<HealthResponse>("/health");

export const loginWithCard = (cardId: string) =>
  request<Resident>("/api/v1/residents/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_id: cardId }),
  });

export const fetchResident = (id: number) =>
  request<Resident>(`/api/v1/residents/${id}`);

export const fetchProducts = () => request<Product[]>("/api/v1/products");

export const fetchInventory = () => request<Product[]>("/api/v1/admin/inventory");

export const fetchCart = (residentId: number) =>
  request<Cart>(`/api/v1/residents/${residentId}/cart`);

export const fetchIotEvents = (limit = 50) =>
  request<IotEvent[]>(`/api/v1/admin/iot-events?limit=${limit}`);

export const fetchDevices = () => request<Device[]>("/api/v1/admin/devices");

/**
 * Event endpoints answer 400/404/409 for rejected packets but still return the full
 * result (validation steps, packet hex, cart). Treat any body with an `accepted`
 * field as a result; anything else is a plain error.
 */
async function requestForResult<T>(
  method: "POST" | "DELETE",
  path: string,
  body: unknown,
  resultKey: string,
): Promise<T> {
  const res = await fetchWithTimeout(
    `${API_BASE_URL}${path}`,
    {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    REQUEST_TIMEOUT_MS,
  );
  const data = await readJson(res);
  if (data && typeof data === "object" && resultKey in data) return data as T;
  throw new ApiError(res.status, describeFailure(res.status, data));
}

const postForResult = (path: string, body: unknown) =>
  requestForResult<CartEventResult>("POST", path, body, "accepted");

/** Simulate a device event; the backend encodes the 16-byte packet. */
export const sendSimulatedEvent = (
  residentId: number,
  event: {
    device_id: number;
    command: CommandName;
    product_code: number;
    weight_grams: number;
  },
) => postForResult(`/api/v1/residents/${residentId}/cart/events`, event);

/** Send a raw hex frame (used for replay / tamper / malformed-packet demos). */
export const sendRawPacket = (residentId: number, packetHex: string) =>
  postForResult(`/api/v1/residents/${residentId}/cart/packets`, { packet_hex: packetHex });

/** Remove a whole product line; the backend sends REMOVE_ITEM packet(s) through the Gateway. */
export const removeCartItem = (residentId: number, productId: number) =>
  requestForResult<RemoveItemResult>(
    "DELETE",
    `/api/v1/residents/${residentId}/cart/items/${productId}`,
    undefined,
    "events",
  );

/** Simulated checkout. A failed payment is HTTP 200 with payment_status FAILED. */
export const checkout = (residentId: number, payment: PaymentSimulation) =>
  request<CheckoutResult>(`/api/v1/residents/${residentId}/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payment_simulation: payment }),
  });

export const fetchAdminOrders = (limit = 20) =>
  request<AdminOrder[]>(`/api/v1/admin/orders?limit=${limit}`);

/** Ask the nutrition assistant. Read-only: it can never change cart, orders, prices or stock. */
export const askNutritionAssistant = (residentId: number, question: string) =>
  request<NutritionResponse>(`/api/v1/residents/${residentId}/nutrition/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  }, NUTRITION_TIMEOUT_MS);
