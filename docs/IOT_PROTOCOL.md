# IoT Protocol: Custom 16-byte Binary Packet

## 1. Purpose

Define a fixed-length application packet for simulated sensor events. The packet represents the payload that could be carried by a Matter Manufacturer Specific Cluster in the proposed Matter-over-Thread architecture.

The course demo implements packet encoding/decoding and gateway validation in Python. The transport itself is simulated; do not claim that a real Matter/Thread network has been deployed.

## 2. Packet layout

Total length: exactly 16 bytes.

| Field | Length | Offset | Description |
|---|---:|---:|---|
| Header | 2 bytes | 0–1 | Fixed magic bytes `0xAA 0x55` |
| Device ID | 2 bytes | 2–3 | Unsigned 16-bit device identifier |
| Sequence Number | 2 bytes | 4–5 | Unsigned 16-bit sequence counter |
| Command | 1 byte | 6 | Event command |
| Payload | 6 bytes | 7–12 | Product code, weight, flags |
| Check Code | 3 bytes | 13–15 | Educational integrity check |

## 3. Payload definition

To remove ambiguity, use this exact six-byte payload:

| Subfield | Length | Description |
|---|---:|---|
| Product Code | 2 bytes | Unsigned 16-bit integer, big-endian |
| Weight | 3 bytes | Unsigned 24-bit integer in grams; `0` means not applicable |
| Flags | 1 byte | Bit flags; bit 0 indicates negative/remove operation if needed, remaining bits reserved |

For the initial demo, prefer command semantics to represent add/remove; therefore the sign flag can remain 0 and be reserved. Do not encode floating-point values.

### Commands
- `0x01`: BIND_CARD
- `0x02`: ADD_ITEM
- `0x03`: REMOVE_ITEM
- `0x04`: CHECKOUT
- `0x05`: ALERT

For `ADD_ITEM` and `REMOVE_ITEM`, `Product Code` and `Weight` are required. For other commands, unused payload fields should be zero unless a later specification defines them.

## 4. Byte order and ranges
- Multi-byte integers use big-endian byte order.
- Device ID: `0..65535`.
- Sequence Number: `0..65535`.
- Product Code: `0..65535`.
- Weight: `0..16777215` grams.
- Packet length must be exactly 16 bytes.

## 5. Check Code (educational only)

The final three bytes are:
- Byte 13: XOR checksum over bytes 0–12.
- Bytes 14–15: 16-bit educational keyed hash value over bytes 0–12 plus a demo secret.

Suggested implementation:
- XOR: XOR every byte from offset 0 through 12.
- Hash-table signature: use a deterministic lookup/mixing table and the demo `SECRET_KEY` to derive a 16-bit value from bytes 0–12.
- Keep the hash-table algorithm deterministic so encoder and decoder produce the same result.
- Put the implementation behind a clearly named function such as `calculate_hash_table_signature(data, secret_key)`.

This preserves the proposal's original XOR + Hash Table design for the course demonstration. It is only an educational tamper-detection exercise: XOR is weak, a 16-bit table-based signature is easy to attack, and neither provides cryptographic authentication. Do not call it production-grade anti-forgery or secure authentication.

If stronger security is explored as an optional extension, compare the educational method with HMAC or AES-CCM in the report; do not silently replace the required course-demo design.

## 6. Sequence number / replay check
- Track the latest accepted sequence number per device.
- Accept only a new sequence number.
- For the simple demo, reject `sequence <= last_sequence`.
- Handle 16-bit wrap-around only if time permits; it is acceptable to document wrap-around as out of scope for the first demo.
- Update `last_sequence` only after the entire packet validation succeeds.
- Add a test proving a repeated packet is rejected.

## 7. Validation order
1. Check input type and exact length (16 bytes).
2. Check magic header.
3. Parse fields.
4. Check supported command.
5. Check XOR and keyed hash.
6. Check sequence number against device state.
7. Check command-specific field constraints.
8. Convert to normalized `IoTEvent`.
9. Only then pass event to cart/business logic.

## 8. Example event
- Device ID: `1`
- Sequence Number: `1`
- Command: `ADD_ITEM` (`0x02`)
- Product Code: `101`
- Weight: `320` grams
- Flags: `0x00`

The encoder must produce exactly 16 bytes. The UI or simulator should display the packet as a 32-character hexadecimal string.

## 9. Required tests
- Valid packet round-trip encode/decode.
- Packet is exactly 16 bytes.
- Wrong header rejected.
- Wrong length rejected.
- Modified payload rejected by check code.
- Unsupported command rejected.
- Replayed sequence rejected.
- Invalid weight or product code rejected.
- Failed validation must not change cart state.

## 10. Protocol layering note
The custom packet is an application payload. In the proposal it is carried inside a Matter Manufacturer Specific Cluster over Matter-over-Thread. In the software demo, a simulated adapter passes the bytes to a Python Gateway. HTTP REST is separately used between the frontend and FastAPI backend.
