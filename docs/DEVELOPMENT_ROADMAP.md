# Development Roadmap

Implement incrementally. Do not generate every feature at once.

## Phase 0 — Repository scaffold
Deliver:
- Frontend and backend folders.
- FastAPI health endpoint.
- React/Vite app shell.
- Docker Compose for PostgreSQL.
- `.env.example`.
- README setup instructions.

Acceptance:
- Backend starts and `/health` returns success.
- Frontend starts and can call backend health endpoint.
- PostgreSQL container starts.

## Phase 1 — Core data and resident flow
Deliver:
- SQLAlchemy models and initial migration or schema creation.
- Seed residents, health profiles, products and devices.
- Resident demo card login.
- Product listing.
- Basic resident and admin screens.

Acceptance:
- `CARD-1001` can log in.
- At least 5 products are visible.
- Resident profile and health preferences display.

## Phase 2 — Custom packet and IoT Gateway
Deliver:
- Python packet encoder/decoder.
- 16-byte fixed format per `IOT_PROTOCOL.md`.
- Simulated Matter-over-Thread transport adapter.
- Gateway validator.
- Sequence state and IoT event audit.
- UI controls to simulate ADD_ITEM / REMOVE_ITEM.

Acceptance:
- Simulator produces 16-byte packet.
- Valid packet updates cart through Gateway.
- Invalid or replayed packet is rejected.
- Packet hex and validation result are visible.

## Phase 3 — Cart and simulated checkout
Deliver:
- Cart service.
- Server-side pricing.
- Remove item flow.
- Simulated payment success/failure.
- Order and order-item persistence.
- Inventory update only after successful payment.

Acceptance:
- Cart total matches backend calculation.
- Failed payment does not create a PAID order or decrement inventory.
- Successful payment creates order and decrements stock.

## Phase 4 — MCP, RAG and nutrition assistant
Deliver:
- Nutrition seed knowledge.
- Retrieval interface.
- MCP tools or a documented MCP-compatible tool layer.
- Mock LLM provider.
- Nutrition recommendation endpoint and UI.
- Optional real LLM provider controlled by environment variables.

Acceptance:
- Assistant can answer using resident preference and retrieved product/nutrition facts.
- Response identifies source snippets or knowledge IDs.
- App works without an external LLM API key.

## Phase 5 — Integration and presentation
Deliver:
- End-to-end demo flow.
- Error states and loading indicators.
- Tests for packet, gateway, cart, checkout.
- Architecture diagram and demo instructions.
- Docker Compose startup path.

Acceptance:
- A clean checkout of the repository can run using documented steps.
- Full demo can be completed without physical hardware or paid external services.

## Claude Code working protocol
At the start of each phase:
1. Read all relevant docs.
2. Inspect existing files.
3. State the implementation plan and files to be changed.
4. Implement only the current phase.
5. Run tests and fix errors.
6. Summarize what changed, how to run it, and known limitations.
7. Stop and wait for the user before moving to the next phase.

Do not silently skip a phase or replace the architecture.
