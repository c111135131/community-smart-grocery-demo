import type {
  AdminOrder, Cart, CartEventResult, CheckoutResult, Device, IotEvent, NutritionResponse,
  Product, Resident, Validation,
} from "../api/types";
import type { Handler } from "./fakeApi";

export const RESIDENT: Resident = {
  resident_id: 1,
  display_name: "Demo Resident",
  health_profile: { dietary_preferences: ["low_sodium"], allergies: [], notes: null },
};

const product = (id: number, code: number, name: string, price: string, stock: number): Product => ({
  id, product_code: code, name, category: "vegetable", price_per_kg: price, stock_grams: stock,
  min_weight_grams: 50, max_weight_grams: 5000, is_active: true,
  nutrition: { summary: `${name}的營養摘要`, per_100g: { sodium_mg: 5 } },
});
export const PRODUCTS: Product[] = [
  product(1, 101, "番茄", "60.00", 20000),
  product(2, 102, "青花菜", "90.00", 15000),
  product(3, 107, "香蕉", "70.00", 16000),
];

export const CART_EMPTY: Cart = { items: [], total_weight_grams: 0, total_amount: "0.00" };
export const CART_ONE: Cart = {
  items: [{ product_id: 1, product_code: 101, name: "番茄", weight_grams: 320, price_per_kg: "60.00", subtotal: "19.20" }],
  total_weight_grams: 320,
  total_amount: "19.20",
};

const ALL_OK: Validation = {
  length_valid: true, header_valid: true, command_valid: true, xor_valid: true, hash_valid: true,
  check_code_valid: true, device_known: true, sequence_valid: true, fields_valid: true, cart_valid: true,
};
export const PACKET_HEX = "AA550001000002006500012C00B4160B";
export const EVENT_OK: CartEventResult = {
  accepted: true, event_id: "evt-1", transport: "SIMULATED Matter-over-Thread (in-process)",
  packet_hex: PACKET_HEX,
  packet: { device_id: 1, sequence_number: 0, command: "ADD_ITEM", product_code: 101, weight_grams: 300, flags: 0 },
  validation: ALL_OK, rejection_code: null, rejection_reason: null, cart: CART_ONE,
};
export const EVENT_REPLAY: CartEventResult = {
  ...EVENT_OK, event_id: "evt-2", accepted: false,
  validation: { ...ALL_OK, sequence_valid: false, fields_valid: null, cart_valid: null },
  rejection_code: "SEQUENCE_REPLAY", rejection_reason: "sequence 0 is not newer than last accepted 0 (replay)",
};
export const EVENT_FORGED: CartEventResult = {
  ...EVENT_OK, event_id: "evt-3", accepted: false,
  validation: { ...ALL_OK, xor_valid: false, hash_valid: false, check_code_valid: false,
    device_known: null, sequence_valid: null, fields_valid: null, cart_valid: null },
  rejection_code: "CHECK_CODE_MISMATCH", rejection_reason: "check code mismatch (packet corrupted or modified)",
};

const receipt = { product_id: 1, product_name: "番茄", price_per_kg: "60.00", weight_grams: 320, subtotal: "19.20" };
export const CHECKOUT_PAID: CheckoutResult = {
  order_id: 7, payment_status: "PAID", total_amount: "19.20", items: [receipt],
  message: "模擬付款成功，訂單已建立並更新庫存", cart: CART_EMPTY,
};
export const CHECKOUT_FAILED: CheckoutResult = {
  order_id: 6, payment_status: "FAILED", total_amount: "19.20", items: [receipt],
  message: "模擬付款失敗，未扣庫存，購物車已保留，可重新結帳", cart: CART_ONE,
};

export const NUTRITION: NutritionResponse = {
  answer: "依據您登記的飲食偏好（低鈉）整理：\n1. 香蕉 [nutrition_seed_013]\n\n※ 以上為一般飲食資訊，不是醫療建議",
  sources: ["nutrition_seed_013"], provider: "mock", notice: null, used_preferences: ["low_sodium"],
  recommended_products: [{ product_code: 107, name: "香蕉", reasons: ["鈉：每 100 公克 1 毫克"] }],
  source_details: [{ id: "nutrition_seed_013", title: "香蕉的營養特色", text: "香蕉含鉀，天然鈉含量極低。" }],
  tool_calls: [{ name: "get_inventory", arguments: { in_stock_only: false }, result_count: 3 }],
};

export const ORDERS: AdminOrder[] = [
  { order_id: 7, resident_id: 1, resident_name: "Demo Resident", total_amount: "19.20", payment_status: "PAID",
    created_at: "2026-11-18T10:00:00Z", items: [receipt] },
  { order_id: 6, resident_id: 1, resident_name: "Demo Resident", total_amount: "19.20", payment_status: "FAILED",
    created_at: "2026-11-18T09:59:00Z", items: [receipt] },
];
export const IOT_EVENTS: IotEvent[] = [
  { id: 2, event_id: "evt-2", resident_id: 1, device_id: 1, sequence_number: 0, command: "ADD_ITEM", product_code: 101,
    weight_grams: 300, packet_hex: PACKET_HEX, validation_status: "REJECTED",
    rejection_reason: "SEQUENCE_REPLAY: replay", created_at: "2026-11-18T10:00:01Z" },
  { id: 1, event_id: "evt-1", resident_id: 1, device_id: 1, sequence_number: 0, command: "ADD_ITEM", product_code: 101,
    weight_grams: 300, packet_hex: PACKET_HEX, validation_status: "ACCEPTED",
    rejection_reason: null, created_at: "2026-11-18T10:00:00Z" },
];
export const DEVICES: Device[] = [
  { id: 1, device_code: "DEV-001", description: "Simulated smart scale", last_sequence_number: 0 },
];

/** Healthy backend: tests override single routes to simulate failures. */
export function healthyRoutes(): Record<string, Handler> {
  return {
    "GET /health": { body: { status: "ok", service: "backend", database: "ok" } },
    "POST /api/v1/residents/login": { body: RESIDENT },
    "GET /api/v1/residents/1": { body: RESIDENT },
    "GET /api/v1/products": { body: PRODUCTS },
    "GET /api/v1/residents/1/cart": { body: CART_EMPTY },
    "GET /api/v1/admin/inventory": { body: PRODUCTS },
    "GET /api/v1/admin/orders": { body: ORDERS },
    "GET /api/v1/admin/iot-events": { body: IOT_EVENTS },
    "GET /api/v1/admin/devices": { body: DEVICES },
  };
}
