# Claude Code Project Instructions

## Project
Build a course-project prototype named **Community Smart Grocery**:
「基於 Matter over Thread 與輕量級防偽封包之社區無人健康生鮮超市系統」

This is an educational integration demo, not a production retail system. Prioritize understandable architecture, working end-to-end integration, and clear demonstrations of:
1. Two communication technologies/protocols at different layers: **Matter over Thread** (device-network architecture; simulated in software-only mode) and **HTTP REST** (implemented for frontend/backend communication).
2. A custom fixed-length **16-byte binary application packet**.
3. IoT event validation and deterministic shopping-cart/order logic.
4. MCP + RAG + LLM Agent as a separable smart-service layer.

## Important scope boundaries
- Do not attempt to build a production-ready unmanned store.
- Do not require physical ESP32, NFC reader, HX711, Thread Border Router, or real payment integration.
- Implement a Python IoT simulator and a software gateway adapter. Clearly label Matter-over-Thread transport as simulated unless real hardware is later added.
- Implement HTTP REST APIs as the working application communication interface.
- Do not add MQTT unless the user explicitly requests it. Do not silently replace the proposed Matter-over-Thread architecture.
- Use a deterministic backend for product prices, weights, cart totals, inventory, and payment status. The LLM must never calculate authoritative prices or update inventory.
- Use mock/simulated payment only.
- Keep the code straightforward and explainable for a university course project. Avoid microservices unless needed; a modular monolith backend is preferred.
- Do not add unnecessary authentication complexity. Use a simple demo resident-card ID flow, with clear comments that it is not production authentication.
- Do not claim XOR/hash-table checks provide cryptographic security. Describe them as educational integrity/replay checks only.

## Preferred implementation
- Frontend: React + TypeScript + Vite; use a simple responsive UI.
- Backend: Python + FastAPI.
- Database: PostgreSQL via Docker Compose; SQLAlchemy 2.x and Alembic if practical. SQLite may be offered as a local fallback, but PostgreSQL is the default.
- IoT simulator/gateway: Python, in a separate module or service.
- AI: isolate behind an AI service interface. Implement a mock provider first so the whole application works without an API key. Add real LLM provider integration only when explicitly configured.
- RAG: use a small local seed knowledge base for nutrition examples. Vector search with pgvector is optional; a simple retrieval adapter is acceptable for the first demo.
- MCP: expose a small set of read-only tools such as `get_product_info`, `get_inventory`, and `search_nutrition_knowledge`. Keep MCP integration isolated and document how to run it.
- Docker Compose should start the minimum required services.

## Development rules
1. Read `docs/SRS.md`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`, `docs/DATABASE.md`, `docs/IOT_PROTOCOL.md`, and `docs/DEVELOPMENT_ROADMAP.md` before coding.
2. Implement in roadmap order. Do not generate the entire application in one huge step.
3. Before editing, inspect the current repository and preserve existing work.
4. Keep business logic in backend services, not React components or LLM prompts.
5. Validate all incoming packet fields and API payloads.
6. Add unit tests for packet encode/decode, checksum verification, sequence-number replay rejection, cart add/remove, and checkout.
7. Use clear names, type hints, docstrings for non-obvious logic, and concise comments.
8. Update README when setup commands or environment variables change.
9. Never commit real API keys. Provide `.env.example`.
10. When a requirement is ambiguous, choose the simplest implementation consistent with the documents and record the assumption in README.

## Definition of done
A working demo should support:
- Resident card login using a seeded card ID.
- View resident health profile and available produce.
- Simulate adding/removing produce by weight.
- Encode a sensor event as the custom 16-byte packet.
- Decode and validate the packet at the gateway, including sequence number and check code.
- Update the cart only after validation succeeds.
- Calculate totals using backend product prices.
- Run simulated checkout.
- Display a nutrition recommendation using mock AI/RAG by default.
- Run locally using documented commands and Docker Compose.
