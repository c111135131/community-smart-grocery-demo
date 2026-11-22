# API Specification (Initial)

Base path: `/api/v1`

All requests and responses use JSON unless otherwise specified. The custom 16-byte packet is sent internally from the simulator adapter to the Gateway module; it is not necessary to expose raw binary as a public browser API.

## 1. Resident

### POST `/residents/login`
Request:
```json
{ "card_id": "CARD-1001" }
```
Response:
```json
{
  "resident_id": 1,
  "display_name": "Demo Resident",
  "health_profile": {
    "dietary_preferences": ["low_sodium"],
    "allergies": []
  }
}
```

### GET `/residents/{resident_id}`
Returns resident profile and health preferences.

## 2. Products

### GET `/products`
Returns active products, unit price per kg, stock weight, category and nutrition summary.

### GET `/products/{product_id}`
Returns one product detail.

## 3. Cart

### GET `/residents/{resident_id}/cart`
Returns current cart items, weights, unit prices and server-calculated subtotals.

### POST `/residents/{resident_id}/cart/events`
Creates a simulated IoT event. Backend must encode the event into the custom packet and pass it through the Gateway validator before changing the cart.

Request:
```json
{
  "device_id": 1,
  "command": "ADD_ITEM",
  "product_code": 101,
  "weight_grams": 320
}
```

Response (illustrative):
```json
{
  "accepted": true,
  "event_id": "evt-demo-001",
  "packet_hex": "AA55...",
  "validation": {
    "header_valid": true,
    "sequence_valid": true,
    "check_code_valid": true
  },
  "cart": {
    "items": [],
    "total_amount": 0
  }
}
```

The response example is schematic; implement actual values and schemas.

### DELETE `/residents/{resident_id}/cart/items/{product_id}`
Removes a product from the cart. For the demo, this may generate a REMOVE_ITEM packet through the same Gateway validation path. Prefer using the same event pathway for add and remove.

## 4. Checkout

### POST `/residents/{resident_id}/checkout`
Request:
```json
{ "payment_simulation": "SUCCESS" }
```
Allowed values: `SUCCESS`, `FAILURE`.

Response:
- Success: order ID, total amount, order status `PAID`.
- Failure: payment status `FAILED`; cart remains available for retry.

## 5. Nutrition assistant

### POST `/residents/{resident_id}/nutrition/recommendations`
Request:
```json
{
  "question": "請推薦適合我的低鈉食材"
}
```
Response:
```json
{
  "answer": "根據目前商品與營養資料，以下是一般飲食資訊建議……",
  "sources": ["nutrition_seed_001"],
  "provider": "mock"
}
```

## 6. Administrator

### GET `/admin/orders`
Returns recent orders.

### GET `/admin/inventory`
Returns product inventory.

## 7. Error handling
Use standard HTTP status codes:
- `400`: invalid request or unsupported command.
- `401`: unknown card ID / demo login failure.
- `404`: resident or product not found.
- `409`: duplicate/replayed sequence or invalid cart state.
- `422`: schema validation failure.
- `500`: unexpected server error.

Do not return internal secrets or stack traces.
