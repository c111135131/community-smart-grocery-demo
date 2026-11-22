// Display labels for codes stored by the backend. Unknown codes fall back to the raw value.
const PREFERENCE_LABELS: Record<string, string> = {
  low_sodium: "低鈉",
  vegetarian: "素食",
};

const ALLERGY_LABELS: Record<string, string> = {
  peanut: "花生",
};

const CATEGORY_LABELS: Record<string, string> = {
  vegetable: "蔬菜",
  fruit: "水果",
  root: "根莖類",
};

export const preferenceLabel = (c: string) => PREFERENCE_LABELS[c] ?? c;
export const allergyLabel = (c: string) => ALLERGY_LABELS[c] ?? c;
export const categoryLabel = (c: string) => CATEGORY_LABELS[c] ?? c;

/** Grams -> "12.5 公斤" / "800 公克" (display only). */
export function formatWeight(grams: number): string {
  return grams >= 1000 ? `${(grams / 1000).toFixed(1)} 公斤` : `${grams} 公克`;
}

/** Backend price string -> "NT$ 60.00" (display only, no calculation). */
export const formatPrice = (price: string) => `NT$ ${price}`;

// ---- Phase 2 ----
export const COMMAND_LABELS: Record<string, string> = {
  ADD_ITEM: "加入商品（ADD_ITEM）",
  REMOVE_ITEM: "移除商品（REMOVE_ITEM）",
  BIND_CARD: "綁定卡片（BIND_CARD，Gateway 尚不支援）",
  CHECKOUT: "結帳（CHECKOUT，Gateway 尚不支援）",
  ALERT: "警示（ALERT，Gateway 尚不支援）",
};

const REJECTION_LABELS: Record<string, string> = {
  INVALID_LENGTH: "封包長度不是 16 bytes",
  INVALID_HEADER: "Magic Header 不是 0xAA55",
  UNSUPPORTED_COMMAND: "不支援的指令",
  CHECK_CODE_MISMATCH: "檢查碼不符（封包遭竄改或損毀）",
  UNKNOWN_DEVICE: "未註冊的裝置",
  SEQUENCE_REPLAY: "序號重複或過舊（疑似重放）",
  INVALID_FIELDS: "欄位內容不合規則",
  PRODUCT_NOT_FOUND: "找不到此商品",
  WEIGHT_OUT_OF_RANGE: "重量超出此商品單次允許範圍",
  INSUFFICIENT_STOCK: "庫存不足",
  ITEM_NOT_IN_CART: "購物車內沒有此商品",
  REMOVE_EXCEEDS_CART: "移除重量大於購物車內重量",
};
export const rejectionLabel = (c: string) => REJECTION_LABELS[c] ?? c;

/** Validation steps in the order the gateway runs them (docs/IOT_PROTOCOL.md section 7). */
export const VALIDATION_STEPS: { key: string; label: string }[] = [
  { key: "length_valid", label: "封包長度為 16 bytes" },
  { key: "header_valid", label: "Magic Header 為 0xAA55" },
  { key: "command_valid", label: "指令為 Gateway 支援" },
  { key: "xor_valid", label: "XOR 檢查碼" },
  { key: "hash_valid", label: "雜湊表簽章（教學用，非密碼學安全）" },
  { key: "device_known", label: "裝置已註冊" },
  { key: "sequence_valid", label: "序號比上次接受的新（防重放）" },
  { key: "fields_valid", label: "指令欄位限制" },
  { key: "cart_valid", label: "購物車規則（商品、重量範圍、庫存、購物車狀態）" },
];

/** Packet field layout for display only (offsets are defined by the backend codec). */
export const PACKET_FIELDS: { name: string; from: number; to: number }[] = [
  { name: "Header", from: 0, to: 2 },
  { name: "裝置 ID", from: 2, to: 4 },
  { name: "序號", from: 4, to: 6 },
  { name: "指令", from: 6, to: 7 },
  { name: "商品代碼", from: 7, to: 9 },
  { name: "重量（公克）", from: 9, to: 12 },
  { name: "Flags", from: 12, to: 13 },
  { name: "XOR", from: 13, to: 14 },
  { name: "雜湊簽章", from: 14, to: 16 },
];

/** Flip one bit inside the weight field so the stale check code no longer matches. */
export function tamperHex(hex: string): string {
  if (hex.length !== 32) return hex;
  const byte = parseInt(hex.slice(22, 24), 16) ^ 0x01;
  return hex.slice(0, 22) + byte.toString(16).padStart(2, "0").toUpperCase() + hex.slice(24);
}

// ---- Phase 3 ----
export const PAYMENT_LABELS: Record<string, string> = {
  PAID: "已付款",
  FAILED: "付款失敗",
};
export const paymentLabel = (s: string) => PAYMENT_LABELS[s] ?? s;

// ---- Phase 4 ----
export const PROVIDER_LABELS: Record<string, string> = {
  mock: "Mock（本地範本，未呼叫外部 LLM）",
  anthropic: "Anthropic（外部 LLM）",
  guardrail: "護欄（未呼叫任何模型）",
};
export const providerLabel = (p: string) => PROVIDER_LABELS[p] ?? p;

export const TOOL_LABELS: Record<string, string> = {
  get_inventory: "查詢庫存與營養（get_inventory）",
  get_product_info: "查詢商品資訊（get_product_info）",
  search_nutrition_knowledge: "檢索營養知識（search_nutrition_knowledge）",
};
export const toolLabel = (n: string) => TOOL_LABELS[n] ?? n;

export const EXAMPLE_QUESTIONS = [
  "請推薦適合我的低鈉食材",
  "哪些蔬菜維生素 C 比較高？",
  "我是素食者，鐵質怎麼補充？",
  "番茄適合我嗎？",
];
