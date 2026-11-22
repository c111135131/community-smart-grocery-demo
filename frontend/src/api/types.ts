// Shapes mirror the backend Pydantic schemas. Money is a string (e.g. "60.00"):
// the frontend only displays prices; the backend is the authority.
export interface HealthResponse {
  status: string;
  service: string;
  database: "ok" | "unavailable";
}

export interface HealthProfile {
  dietary_preferences: string[];
  allergies: string[];
  notes: string | null;
}

export interface Resident {
  resident_id: number;
  display_name: string;
  health_profile: HealthProfile;
}

export interface Nutrition {
  summary?: string;
  per_100g?: {
    calories_kcal?: number;
    sodium_mg?: number;
    fiber_g?: number;
    vitamin_c_mg?: number;
    potassium_mg?: number;
  };
}

export interface Product {
  id: number;
  product_code: number;
  name: string;
  category: string;
  price_per_kg: string;
  stock_grams: number;
  min_weight_grams: number;
  max_weight_grams: number;
  nutrition: Nutrition;
  is_active: boolean;
}

// ---- Phase 2: cart + IoT gateway ----
// Money values are strings from the backend (e.g. "19.20"); the UI only displays them.
export interface CartItem {
  product_id: number;
  product_code: number;
  name: string;
  weight_grams: number;
  price_per_kg: string;
  subtotal: string;
}

export interface Cart {
  items: CartItem[];
  total_weight_grams: number;
  total_amount: string;
}

export type CommandName = "BIND_CARD" | "ADD_ITEM" | "REMOVE_ITEM" | "CHECKOUT" | "ALERT";

export interface ParsedPacket {
  device_id: number;
  sequence_number: number;
  command: string;
  product_code: number;
  weight_grams: number;
  flags: number;
}

/** null = that validation step was never reached. */
export interface Validation {
  length_valid: boolean | null;
  header_valid: boolean | null;
  command_valid: boolean | null;
  xor_valid: boolean | null;
  hash_valid: boolean | null;
  check_code_valid: boolean | null;
  device_known: boolean | null;
  sequence_valid: boolean | null;
  fields_valid: boolean | null;
  cart_valid: boolean | null;
}

export interface CartEventResult {
  accepted: boolean;
  event_id: string;
  transport: string;
  packet_hex: string;
  packet: ParsedPacket | null;
  validation: Validation;
  rejection_code: string | null;
  rejection_reason: string | null;
  cart: Cart;
}

export interface IotEvent {
  id: number;
  event_id: string;
  resident_id: number | null;
  device_id: number | null;
  sequence_number: number | null;
  command: string | null;
  product_code: number | null;
  weight_grams: number | null;
  packet_hex: string;
  validation_status: "ACCEPTED" | "REJECTED";
  rejection_reason: string | null;
  created_at: string;
}

export interface Device {
  id: number;
  device_code: string;
  description: string;
  last_sequence_number: number;
}

// ---- Phase 3: remove item, checkout, orders ----
export interface RemoveItemResult {
  accepted: boolean;
  events: CartEventResult[];
  cart: Cart;
}

export type PaymentSimulation = "SUCCESS" | "FAILURE";

export interface OrderItem {
  product_id: number;
  product_name: string;
  price_per_kg: string;
  weight_grams: number;
  subtotal: string;
}

export interface CheckoutResult {
  order_id: number;
  payment_status: "PAID" | "FAILED";
  total_amount: string;
  items: OrderItem[];
  message: string;
  cart: Cart;
}

export interface AdminOrder {
  order_id: number;
  resident_id: number;
  resident_name: string;
  total_amount: string;
  payment_status: "PAID" | "FAILED";
  created_at: string;
  items: OrderItem[];
}

// ---- Phase 4: nutrition assistant (mock AI + RAG + read-only MCP-style tools) ----
export interface SourceSnippet {
  id: string;
  title: string;
  text: string;
}

export interface RecommendedProduct {
  product_code: number;
  name: string;
  reasons: string[];
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result_count: number;
}

export interface NutritionResponse {
  answer: string;
  sources: string[];
  provider: "mock" | "anthropic" | "guardrail" | string;
  notice: string | null;
  used_preferences: string[];
  recommended_products: RecommendedProduct[];
  source_details: SourceSnippet[];
  tool_calls: ToolCall[];
}
