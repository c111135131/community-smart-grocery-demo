# Community Smart Grocery

**課堂專題：基於 Matter over Thread 與輕量級防偽封包之社區無人健康生鮮超市系統**

本專題以社區型無人健康生鮮超市為情境，整合 IoT 裝置資料、通訊架構、自訂二進位封包、後端交易邏輯與 AI 營養服務。

> 專題定位：以軟體模擬完成端到端整合，理解必要基礎架構；不是可直接商業上線的零售系統。

## 技術展示重點

1. **Matter over Thread**：作為 IoT 裝置網路的目標架構。第一階段以 Python Simulator + Gateway Adapter 模擬裝置與 Gateway 的資料流，不宣稱已建立真實 Thread Mesh。
2. **HTTP REST**：實際用於前端與 FastAPI 後端之間的 API 通訊。
3. **自訂 16-byte Binary Packet**：模擬感測器事件封包，於 Gateway 進行解析、基本完整性檢查及序號重放檢查。
4. **MCP + RAG + LLM Agent**：提供商品、庫存與營養知識查詢，支援個人化營養建議。

## 系統分層

- Layer 1 — 感知與互動：居民 Web/LINE LIFF 概念介面、管理介面、感測器模擬器。
- Layer 2 — 網路通訊：Matter over Thread 架構概念、自訂 Manufacturer Specific Cluster payload。
- Layer 3 — Gateway 與驗證：封包解析、Sequence Number、XOR / 教學用 hash check、重量與商品資料檢查。
- Layer 4 — 智慧服務：MCP、RAG、LLM Agent、健康資料與營養建議。
- Data — PostgreSQL：居民、商品、庫存、購物車、訂單與交易紀錄。

## 專題範圍與誠實標示

- 不需要實體 ESP32、NFC、HX711 或 Thread Border Router。
- 不串接真實金流。
- 不要求真正完成 Matter 裝置配對與 Thread Mesh 網路。
- XOR / 小型 hash check 僅為教學用途，不能視為密碼學安全或真正防偽。
- AI 輸出僅供一般飲食資訊參考，不提供醫療診斷或治療建議。

## 文件

- `CLAUDE.md`：Claude Code 開發規則。
- `docs/SRS.md`：需求規格。
- `docs/ARCHITECTURE.md`：系統架構與資料流。
- `docs/API_SPEC.md`：REST API 規格草案。
- `docs/DATABASE.md`：資料庫設計。
- `docs/IOT_PROTOCOL.md`：16-byte 封包格式與驗證流程。
- `docs/DEVELOPMENT_ROADMAP.md`：開發順序與驗收標準。
- `docs/DEMO_GUIDE.md`：講稿式 Demo 流程、Q&A 與出狀況時的處理。
- `docs/DIAGRAMS.md`、`docs/architecture.svg`：依實際建置繪製的架構與流程圖。

## 架構圖

![實際建置架構](docs/architecture.svg)

虛線 = 模擬的硬體／傳輸（沒有真實 ESP32、Thread、Matter）；實線 = 已實作的軟體；藍色 = AI 層，對交易資料唯讀。
封包格式、Gateway 驗證流程、結帳時序、助理流程與 Docker 拓樸見 [`docs/DIAGRAMS.md`](docs/DIAGRAMS.md)。

## 快速開始（Docker Compose，建議）

只需要 Docker（含 Compose v2），不必安裝 Python 或 Node：

```bash
cp .env.example .env          # 可省略；compose 的預設值與它相同
docker compose up --build
```

第一次建置需要數分鐘。完成後：

| 網址 | 內容 |
|---|---|
| <http://localhost:5173> | 網頁介面（登入卡號 `CARD-1001` 或 `CARD-1002`） |
| <http://localhost:8000/docs> | API 文件 |

- 後端容器啟動時會**自動等待資料庫、執行 migration 並寫入示範資料**；重啟容器不會重置資料或庫存。
- 驗證整個系統（約 2 秒，只需要 Python 3 標準函式庫）：`python scripts/demo_smoke.py`
  （會真的修改示範資料，見下方「Demo 流程」）。
- 重置所有資料：`docker compose down -v`。
- 三個 port 都只綁定 `127.0.0.1`（示範用密碼、管理端沒有驗證），請勿對網路開放。

| 常見問題 | 處理 |
|---|---|
| port 5432 / 8000 / 5173 被占用 | 關閉占用的程式；資料庫 port 可改 `.env` 的 `POSTGRES_PORT`。若改了後端或前端 port，也要同步修改 `CORS_ORIGINS` 與 `VITE_API_BASE_URL` |
| 改了程式碼卻沒生效 | `docker compose up --build` 重新建置 |
| 改了 `VITE_API_BASE_URL` | 它在**建置時**寫入前端，必須重新建置；且要填**瀏覽器**連得到的網址 |
| 看後端記錄 | `docker compose logs -f backend` |
| 前端顯示「後端離線」 | 先確認 `docker compose ps` 中 backend 為 healthy |

> **驗證狀態（請讀）**：撰寫環境沒有 Docker，也連不到 Docker Hub，所以 `docker build` 與 `docker compose up`
> **沒有實際執行過**。我改用等價方式驗證：在乾淨目錄用 `requirements.txt` 建新 venv，並執行與容器相同的
> entrypoint 腳本（含「資料庫尚未就緒」競爭、重啟保留資料、資料庫永遠起不來等情境）；用 `npm ci` 加真正的 nginx
> 與同一份 `nginx.conf` 提供建置結果；另有 `backend/tests/test_deploy_config.py` 靜態檢查 Dockerfile 與 compose。
> 它們驗證不到的部分（`FROM` 映像、`useradd`、容器網路與 DNS、容器內的 healthcheck）請在您的機器上第一次執行時留意。

## Demo 流程

完整講稿（約 8–10 分鐘，含預期畫面、可能被問的問題與出狀況時的處理）見 [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md)。重點流程：

1. 居民卡號登入 → 顯示健康偏好與商品。
2. 營養助理：依偏好、營養數據與知識庫回答，列出來源知識 ID 與使用的唯讀工具。
3. IoT 模擬器送出 ADD_ITEM → 16-byte 封包、欄位拆解、9 步驗證 → 購物車更新，**價格由後端計算**。
4. 重放與竄改封包被拒絕，並指出是哪一步失敗；購物車不變。
5. 移除商品、模擬付款失敗（保留購物車、不扣庫存）、再模擬付款成功（收據、扣庫存）。
6. 管理頁：訂單（含失敗）、Gateway 稽核（含被拒絕的封包）、裝置序號。
7. 要求助理「幫我結帳」→ 護欄拒絕，資料不變。

`scripts/demo_smoke.py` 會對執行中的系統自動走完上述流程並逐步斷言（42 項）。**它是真實執行，不是試跑**：
會清空該卡片的購物車、建立一筆 PAID 與一筆 FAILED 訂單、消耗裝置序號、並把兩項商品庫存減少數百公克。
展示前請先跑一次確認，再重置資料。

## 本機開發（後端與前端在本機執行）

只讓資料庫跑在 Docker（`docker compose up -d db`），後端與前端直接在本機執行，方便除錯與修改程式。

### 前置需求

- Docker（含 Docker Compose v2）
- Python 3.11+
- Node.js 20+（含 npm）

### 1. 設定環境變數

```bash
cp .env.example .env
```

`.env` 已列入 `.gitignore`，請勿提交真實金鑰。範例中的帳密僅供本機 demo。

| 變數 | 說明 | 預設值 |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | PostgreSQL 帳密與資料庫名稱 | `grocery` / `grocery_demo_pw` / `community_grocery` |
| `POSTGRES_PORT` | 對外連接埠 | `5432` |
| `DATABASE_URL` | 後端連線字串 | `postgresql+psycopg://grocery:...@localhost:5432/community_grocery` |
| `CORS_ORIGINS` | 允許的前端來源（逗號分隔） | `http://localhost:5173,http://127.0.0.1:5173` |
| `VITE_API_BASE_URL` | 前端呼叫的後端位址 | `http://localhost:8000` |
| `IOT_SECRET_KEY` | 封包雜湊簽章用的**教學示範金鑰**（非密碼學安全） | `demo-secret-not-for-production` |
| `AI_PROVIDER` | 營養助理提供者：`mock`（預設，不需金鑰）或 `anthropic` | `mock` |
| `ANTHROPIC_API_KEY` / `AI_MODEL` | 僅在 `AI_PROVIDER=anthropic` 時需要，兩者缺一就改用 mock；**請勿提交真實金鑰** | 空 |
| `AI_TIMEOUT_SECONDS` | 呼叫外部 LLM 的逾時秒數 | `20` |
| `KNOWLEDGE_BASE_PATH` | 自訂知識庫 JSON 路徑（選填） | `knowledge_base/nutrition_seed.json` |

### 2. 啟動 PostgreSQL

```bash
docker compose up -d db
docker compose ps        # 狀態應為 healthy
```

### 3. 啟動後端（FastAPI）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head               # 建立資料表（初始 migration）
python -m app.seed                 # 寫入示範資料（可重複執行，不覆蓋既有資料）
uvicorn app.main:app --reload --port 8001
```

驗證：`curl http://localhost:8001/health` 應回傳

```json
{"status":"ok","service":"community-smart-grocery-backend","database":"ok"}
```

API 文件：<http://localhost:8001/docs>

### 4. 啟動前端（React + Vite）

```bash
cd frontend
npm install
npm run dev
```

開啟 <http://localhost:5173>，畫面會顯示後端 API 與 PostgreSQL 的連線狀態。

### 5. 登入並操作 Demo

開啟 <http://localhost:5173>：

- 居民頁：輸入 `CARD-1001`（低鈉）或 `CARD-1002`（素食、花生過敏）登入，可看到健康偏好與 8 項生鮮商品。
- 管理頁：唯讀的商品庫存、最近訂單與 IoT 稽核（示範用，無管理員驗證）。

> 識別卡登入只是模擬刷卡，**不是**正式身分驗證；管理頁亦未設驗證。

### 6. 操作 IoT 模擬器（Phase 2）

登入後在居民頁的「IoT 智慧秤模擬器」選擇指令、商品與重量，按「送出封包」：

1. 後端以模擬裝置編碼成 16-byte 封包，經**軟體模擬**的 Matter-over-Thread 傳輸送到 Gateway。
2. Gateway 依序驗證，通過後才更新購物車；畫面顯示封包十六進位、欄位拆解與每一步驗證結果。
3. 展開「進階：重放與竄改封包演示」：重送相同封包會因序號被拒絕；竄改重量會因檢查碼被拒絕。
4. 管理頁的「IoT Gateway 稽核」列出每個到達 Gateway 的封包（含被拒絕者）與裝置最後序號。

也可以不用資料庫，直接用 CLI 產生封包十六進位（再貼到「自訂十六進位封包」）：

```bash
cd backend
python -m app.simulator --device 1 --seq 1 --command ADD_ITEM --product 101 --weight 320
# packet_hex : AA550001000102006500014000D9847C
```

### 7. 購物車、結帳與訂單（Phase 3）

1. 用模擬器加入商品後，購物車顯示每公斤單價、小計與總額（全部由後端計算）。
2. 「移除」按鈕會由後端送出一個或多個 `REMOVE_ITEM` 封包，經同一條 Gateway 路徑處理並寫入稽核。
3. 結帳區選擇**模擬付款結果**：
   - 付款成功：建立 `PAID` 訂單與明細、扣庫存、清空購物車，畫面顯示收據。
   - 付款失敗：保留購物車、不扣庫存，可重試；失敗嘗試會以 `FAILED` 訂單留存供稽核。
4. 管理頁的「最近訂單」可看到已付款與失敗的訂單。

### 8. 營養助理與 MCP（Phase 4）

居民頁的「營養助理」可直接提問（預設 mock，**不需要任何 API key**）：

- 回答依據居民的飲食偏好、資料庫中的商品營養數值與知識庫片段；商品推薦由後端決定性邏輯產生。
- 回應列出**參考來源**（知識 ID 與片段內容）、助理使用過的唯讀工具與提供者。
- 要求結帳、改價格或改庫存等交易時，助理會拒絕且不呼叫任何模型（提供者顯示「護欄」），資料不會變動。

**MCP server**（外部 MCP client 可使用同一組唯讀工具）：

```bash
cd backend
python -m app.ai.mcp_server        # stdio；通常由 MCP client 啟動，需先啟動並 seed 資料庫
```

提供 3 個工具，皆標示唯讀：`get_product_info(product_code)`、`get_inventory(in_stock_only, category)`、
`search_nutrition_knowledge(query, limit, tags)`。MCP client 設定範例（路徑請改成您的實際路徑）：

```json
{
  "mcpServers": {
    "community-grocery": {
      "command": "/ABS/PATH/backend/.venv/bin/python",
      "args": ["-m", "app.ai.mcp_server"],
      "cwd": "/ABS/PATH/backend"
    }
  }
}
```

若您的 client 不支援 `cwd`，可改用 `"command": "sh", "args": ["-c", "cd /ABS/PATH/backend && .venv/bin/python -m app.ai.mcp_server"]`。
本專案只用官方 MCP Python SDK 的 stdio client 驗證過（見 `backend/tests/test_ai_mcp_server.py`）。
這個 server 沒有驗證機制也沒有居民資料，**只應由受信任的本機 client 以 stdio 啟動，不要對網路開放**。

**選用真實 LLM**（在 `.env` 設定，沒設定就一律使用 mock）：

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=...        # 請勿提交
AI_MODEL=...                 # 模型 ID，必填
```

呼叫失敗（逾時、HTTP 錯誤、回應格式錯誤）會自動退回 mock，並在回應的 `notice` 說明原因。

### 9. 執行測試

```bash
cd backend  && pytest              # 301 項；使用記憶體 SQLite，不需要資料庫或網路
cd frontend && npm test            # 51 項；以假的 fetch 取代後端，不需要後端
python scripts/demo_smoke.py       # 對「執行中」的完整系統做端到端檢查（會修改資料）
```

後端測試**不依賴任何外部服務**：已用「PostgreSQL 完全停止」的情況驗證全部通過。
MCP 整合測試會啟動子行程，約需數秒。涵蓋率（後端 97%，不含在子行程執行的 CLI 與 MCP server）：
`pip install coverage && coverage run --source=app -m pytest && coverage report`。

| 領域（`CLAUDE.md` 要求） | 主要測試檔（`backend/tests/`） |
|---|---|
| 封包編碼／解碼、檢查碼 | `test_packet.py`（含固定的標準範例封包） |
| Gateway 驗證與序號重放 | `test_gateway_validator.py`、`test_cart_events.py`、`test_transport.py` |
| 購物車新增／移除 | `test_cart_events.py`、`test_cart_remove.py` |
| 計價與結帳（成功／失敗／回滾／庫存） | `test_pricing.py`、`test_checkout.py` |
| AI：知識庫、檢索、唯讀工具、MCP、提供者、護欄 | `test_ai_*.py`、`test_nutrition_api.py` |
| 端到端 Demo | `test_e2e_demo.py`（同一份 `scripts/demo_smoke.py`） |
| 失敗路徑與維運程式 | `test_robustness.py`（Gateway 回滾、等待資料庫、CLI…） |
| Docker／compose 設定 | `test_deploy_config.py`（靜態檢查，不需 Docker） |
| 前端：錯誤狀態、載入指示、重試、結帳、封包驗證顯示 | `frontend/src/test/*.test.ts(x)` |

我另外用**變異測試**確認關鍵測試真的有效：故意破壞重放檢查、序號消耗、結帳扣庫存、付款狀態、四捨五入規則、
AI 護欄與回退、部署設定等，測試都會失敗。過程中也因此抓到過幾個真正的缺陷與無效的測試並已修正。

### 驗證 migration 與 PostgreSQL

```bash
cd backend
alembic upgrade head && alembic check     # 應顯示 "No new upgrade operations detected."
python -m app.seed
curl -X POST http://localhost:8000/api/v1/residents/login \
     -H 'Content-Type: application/json' -d '{"card_id":"CARD-1001"}'
```

重設資料庫：`docker compose down -v` 後重新執行步驟 2、3。

## API

Base path `/api/v1`，詳見 `docs/API_SPEC.md`。

| Method | Path | 說明 |
|---|---|---|
| POST | `/residents/login` | 以卡號登入；未知卡號回 401，格式錯誤回 422 |
| GET | `/residents/{id}` | 居民資料與健康偏好；不存在回 404 |
| GET | `/products` | 上架中的商品 |
| GET | `/products/{id}` | 單一商品；不存在或已下架回 404 |
| GET | `/admin/inventory` | 全部商品與庫存（含已下架） |
| GET | `/residents/{id}/cart` | 購物車（含單價、小計與總額，由後端計算） |
| POST | `/residents/{id}/cart/events` | 模擬裝置事件；後端編碼成 16-byte 封包再送入 Gateway |
| POST | `/residents/{id}/cart/packets` | 示範用：直接送十六進位封包（重放／竄改／格式錯誤演示） |
| GET | `/admin/iot-events` | Gateway 稽核紀錄（新到舊，`limit` 1–200） |
| GET | `/admin/devices` | 裝置與最後接受序號 |
| DELETE | `/residents/{id}/cart/items/{product_id}` | 移除整個商品項目；以 `REMOVE_ITEM` 封包經 Gateway 完成（可選 `?device_id=`，預設 1） |
| POST | `/residents/{id}/checkout` | 模擬結帳，body：`{"payment_simulation": "SUCCESS" \| "FAILURE"}` |
| GET | `/admin/orders` | 最近訂單（含 `FAILED`），`limit` 1–200 |
| POST | `/residents/{id}/nutrition/recommendations` | 營養助理，body：`{"question": "..."}`（1–500 字）；居民不存在回 404 |

事件端點被拒絕時**仍回傳完整結果本體**（封包、每步驗證、購物車），僅狀態碼不同：

| 狀態碼 | 拒絕原因（`rejection_code`） |
|---|---|
| 200 | 已接受 |
| 400 | `INVALID_LENGTH`、`INVALID_HEADER`、`UNSUPPORTED_COMMAND`、`CHECK_CODE_MISMATCH`、`UNKNOWN_DEVICE`、`INVALID_FIELDS`、`WEIGHT_OUT_OF_RANGE` |
| 404 | `PRODUCT_NOT_FOUND`（居民或裝置不存在則回 `{"detail": ...}`） |
| 409 | `SEQUENCE_REPLAY`、`INSUFFICIENT_STOCK`、`ITEM_NOT_IN_CART`、`REMOVE_EXCEEDS_CART`；結帳時購物車為空、商品已下架或庫存不足 |
| 422 | 請求格式不合（例如非十六進位字元） |

價格（`price_per_kg`）以字串傳輸（如 `"60.00"`），避免浮點誤差；前端只負責顯示。

## 目前進度

- [x] Phase 0 — Repository scaffold
- [x] Phase 1 — Core data and resident flow
- [x] Phase 2 — Custom packet and IoT Gateway
- [x] Phase 3 — Cart and simulated checkout
- [x] Phase 4 — MCP, RAG and nutrition assistant
- [x] Phase 5 — Integration and presentation

## 驗證狀態與已知限制總表

| 項目 | 狀態 |
|---|---|
| 後端 301 項、前端 51 項自動化測試 | 通過 |
| 在真實 PostgreSQL 16 驗證 migration、並行結帳、並行 IoT 事件、MCP server | 通過（手動，非自動化測試） |
| `scripts/demo_smoke.py` 42 項端到端檢查（含在模擬容器環境的全新資料庫上） | 通過 |
| `docker build` / `docker compose up` | **未實際執行**（無 Docker）；已用等價步驟與靜態測試驗證，見上方 Docker 區塊 |
| 真實瀏覽器的畫面外觀與互動 | **未驗證**；UI 只用 jsdom 與 Testing Library 驗證行為 |
| 真實 LLM（Anthropic）呼叫 | **從未對真實服務發出請求**；只用模擬傳輸層測過請求格式與錯誤處理 |
| 其他 MCP client | 只用官方 Python SDK 的 stdio client 驗證過 |
| Mermaid 圖 | 語法經官方解析器驗證；視覺渲染未驗證（SVG 已渲染檢視） |
| Windows / macOS | 未測試（撰寫環境為 Linux） |
| 效能、負載、資安測試 | 未進行 |

**這不是可上線的系統**：沒有管理員驗證、居民登入只是模擬刷卡、檢查碼不具密碼學安全性、不串接真實金流、
沒有真實的 Matter / Thread / 硬體、營養知識庫未經專業審閱、AI 輸出僅供一般飲食資訊參考。
各階段的細節假設如下。

## 實作假設與已知限制

- `/health` 只要 API 程序存活就回傳 HTTP 200；PostgreSQL 連線狀態另以 `database` 欄位（`ok` / `unavailable`）呈現，避免資料庫尚未啟動時後端無法診斷。
- 初始 migration 依 `docs/DATABASE.md` 一次建立全部 9 張表（`iot_events` 於 migration 0002 調整，見 Phase 2 說明）。

### Phase 2 假設與限制

- **傳輸為軟體模擬**：沒有真實 Matter、Thread、Border Router 或 ESP32/HX711 硬體。`SimulatedMatterThreadTransport` 只是行程內呼叫，並實作 `MatterTransportAdapter` 介面，日後可替換。
- **檢查碼僅供教學**：XOR 與 16-bit 雜湊表簽章（`calculate_hash_table_signature`）不具密碼學安全性，不可視為防偽造或身分驗證；`IOT_SECRET_KEY` 是示範金鑰。實際抵禦重放靠序號，而非檢查碼。
- **iot_events 結構調整**（migration 0002）：新增 `sequence_number`，並讓 `device_id`、`command`、`product_code`、`weight_grams` 可為空、`packet_hex` 改為 Text，否則長度或 Header 錯誤的封包無法稽核。
- **序號何時消耗**：封包通過 Gateway 全部檢查即更新 `last_sequence_number`，即使購物車之後因商品不存在、庫存不足等業務原因拒絕；任何 Gateway 檢查失敗則不更新。模擬裝置的下一個序號 = 最後接受序號 + 1，避免後端重啟後與資料庫不同步。
- **序號不回捲**：16-bit 序號用盡（65535）後回 409，示範未實作回捲。
- **並行安全**：同一裝置的事件以資料列鎖（`SELECT … FOR UPDATE`）序列化；已在 PostgreSQL 以 12 個並行請求驗證序號不重複、購物車重量正確。
- **Gateway 目前只處理 `ADD_ITEM` / `REMOVE_ITEM`**；`BIND_CARD`、`CHECKOUT`、`ALERT` 編碼器認得，但 Gateway 以 `UNSUPPORTED_COMMAND` 拒絕。`flags` 目前必須為 0。
- **REMOVE_ITEM 語意**：扣除指定重量；商品不在購物車或扣除量大於現有量都會拒絕，剛好扣完則移除該項目。ADD_ITEM 使購物車超過庫存會被拒絕。單次重量範圍規則見 Phase 3 說明（最小重量只限制 ADD_ITEM）。
- `POST /cart/packets` 為 API_SPEC 以外新增的示範端點，用來送出任意位元組；正式系統不應對瀏覽器開放。
- 模擬器放在 `backend/app/simulator/`（而非最上層 `simulator/`），因後端需直接呼叫；最上層目錄僅留說明。
- 示範裝置固定使用 `device_id = 1`（seed 的 `DEV-001`）。
- Seed 的營養數值為教學用的四捨五入近似值，非權威營養資料；人名、庫存皆為虛構。
- 居民登入後僅在瀏覽器 `sessionStorage` 保存居民 ID（重新整理後還原），不含任何憑證。
- 單元測試以 SQLite 記憶體資料庫執行（模型使用 JSON/JSONB 變體），PostgreSQL 行為以 `alembic check` 與實際啟動驗證。
- 前端以環境變數 `VITE_API_BASE_URL` 直接呼叫後端，並由後端 CORS 設定放行 Vite 開發伺服器來源。

### Phase 3 假設與限制

- **金額規則**：`小計 = 單價 × 公克 ÷ 1000`，每列四捨五入到小數 2 位（ROUND_HALF_UP，14.985 → 14.99）；**總額 = 各列已進位小計的加總**，所以收據每列相加必等於總額。重量為整數公克、金額為 Decimal，全程不用浮點數；API 以字串傳輸金額（如 `"19.20"`）。
- **付款失敗會留下 `FAILED` 訂單**（含明細快照，供管理員稽核），但不扣庫存、不清購物車；`orders.payment_status` 本來就允許 `FAILED`。多次失敗會產生多筆 `FAILED` 紀錄。
- **付款失敗回 HTTP 200**（`payment_status: "FAILED"`），因為它是正常業務結果；HTTP 409 代表購物車根本無法結帳（空購物車、商品已下架、庫存不足），此時不會建立任何訂單。
- **結帳是單一資料庫交易**：先鎖購物車列、再依商品 id 排序鎖商品列（避免死結），驗證後建立訂單、扣庫存、清購物車，任何錯誤整筆回滾；已用測試強制在 commit 前拋錯驗證。IoT 事件修改購物車時也鎖同一列，兩者不會互相踩踏。
- **庫存只在付款成功後扣除**；結帳時會重新檢查庫存（另一位居民可能已買走），不足則 409 且購物車保留。
- **訂單明細是快照**（商品名稱與單價），之後商品改價或改名不影響歷史訂單。
- **修正 Phase 2 的缺口**：最小單次重量限制現在只限制 `ADD_ITEM`；`REMOVE_ITEM` 只受最大單次重量與「不超過購物車內重量」限制，否則剩 30 公克的項目永遠移不掉。已下架商品仍可從購物車移除，避免購物車卡死。
- **`DELETE /cart/items/{id}` 以多個 `REMOVE_ITEM` 封包完成**：購物車重量超過商品單次上限時分批送出（例如 11234 公克 → 5000 + 5000 + 1234），每個封包都經 Gateway 驗證、取得新序號並寫入稽核。若中途某個封包被拒絕則停止，已成功的批次不會回復。
- 結帳只有模擬付款，**沒有**任何真實金流整合、發票或退款。
- 尚無居民端的歷史訂單查詢（規格只要求管理員的 `GET /admin/orders`）。

### Phase 4 假設與限制

- **MCP 是真的，但站內助理不走 MCP 通訊協定**：`backend/app/ai/mcp_server.py` 是用官方 SDK（`mcp>=2.3,<3`）寫的 stdio MCP server；站內助理則在同一個行程內直接呼叫同一個 `ToolBox`，因為每個請求都開子行程太慢也太脆弱。兩邊工具清單與描述由測試保證一致。若要讓助理改走 MCP，只需替換 `ToolRunner` 的呼叫端。
- **推薦由後端決定，LLM 只負責措辭**：`recommender.py` 依營養數值與居民偏好排序商品（重點由問題決定，例如「維生素 C」「低鈉」，否則由偏好推得，最後預設為膳食纖維）。LLM 拿到的是已定案的事實，無法更動推薦清單。
- **LLM 拿不到價格與庫存數量**，所以不可能報錯或計算價格；也不會收到姓名與卡號。送出的只有飲食偏好、過敏原、最近付款成功的商品名稱、營養事實與檢索到的知識片段。使用真實 LLM 時，這些資料會離開本機，畫面也會提示。
- **`sources` 由後端決定**：回應的來源是實際提供給提供者的知識 ID，而不是 LLM 自己宣稱引用的 ID，避免編造引用。
- **護欄**：問題含結帳、付款、退款、下單、改價格、改庫存等交易意圖時，不呼叫模型，直接回覆無法執行（`provider: "guardrail"`）。這是以規則比對實作，會漏掉刻意迴避的措辭；真正的保證來自架構：助理沒有任何寫入工具，也不會寫入資料庫（已用測試比對助理前後的資料庫狀態）。
- **過敏原**：商品資料沒有過敏原欄位，助理只會說明「無法判斷商品是否含過敏原，請自行確認標示」，不會宣稱安全。商品營養資料也沒有鐵、蛋白質、B12 等欄位，被問到時會明說，而不是改用別的指標假裝回答。
- **檢索是本地簡化實作**（關鍵字、標籤與中文字元雙連詞 TF-IDF 的加權），沒有使用 pgvector 或 embedding；`Retriever` 介面可日後替換。對同義詞與口語改寫的辨識能力有限。
- **知識庫內容是一般性示範資料，未經營養師審閱**，不具醫療效力。`low_sodium` 的商品篩選門檻（每 100 公克鈉 ≤ 60 毫克，僅在問題不是以鈉為主時套用）是示範用數字，不是醫療標準。
- **真實 LLM 只實作 Anthropic Messages API**（以 httpx 直接呼叫，無額外 SDK）。**我沒有 API 金鑰，因此從未對真實服務發出過請求**；請求格式、標頭、回應解析與各種錯誤都只用模擬傳輸層測試過。第一次使用時請自行驗證 `AI_MODEL` 與實際回應。
- **提供者失敗一律退回 mock**，`notice` 只包含簡短原因（如 `HTTP 500`、`request timed out`），絕不包含回應內容或金鑰。
- 回應欄位比 `docs/API_SPEC.md` 的範例多（`recommended_products`、`source_details`、`tool_calls`、`notice`、`used_preferences`），屬於向下相容的擴充。
- `core/database.py` 現在對 SQLite 不帶 `connect_timeout`（MCP 整合測試使用暫存 SQLite 檔）；預設資料庫仍是 PostgreSQL。
- MCP 整合測試會啟動子行程（`python -m app.ai.mcp_server`），約需數秒。

### Phase 5 假設與限制

- **Docker**：compose 以專案根目錄為建置 context（為了複製 `knowledge_base/`）；三個服務的 port 都只綁定 `127.0.0.1`。
  這也把 Phase 0 資料庫原本綁定所有網卡的 port 設定改為只綁 localhost。
- 後端容器由 `backend/scripts/docker-entrypoint.sh` 啟動：等待資料庫（預設最多 60 秒，可用 `DB_WAIT_TIMEOUT` 調整）→
  `alembic upgrade head` → `python -m app.seed` → `uvicorn`。逾時則以 exit code 1 結束，容器不會在沒有資料庫的情況下啟動。
- 後端映像包含 `pytest` 等開發依賴（單一 `requirements.txt`），為了簡化；正式環境應拆分。
- 前端是 nginx 提供的靜態建置結果，瀏覽器**直接呼叫後端**（不經 nginx 代理），所以後端 `CORS_ORIGINS` 必須包含前端網址。
- 前端請求逾時：一般 15 秒、營養助理 30 秒；逾時、離線、5xx 都顯示友善訊息，5xx **不會**顯示後端內部訊息。
- 前端測試與測試依賴（`vitest`、`jsdom`、Testing Library）屬於 `devDependencies`，不會進入建置產物（已確認 bundle 不含測試程式碼）。
  測試也會被 `tsc -b` 型別檢查，所以測試程式碼必須符合專案的 ES2020 目標。
- 前一版的一個缺陷已修正：居民頁在商品載入失敗、購物車載入成功時，錯誤訊息會被誤清掉。現在兩者獨立記錄。
- 模擬器 CLI 對超出欄位範圍的數值現在顯示錯誤訊息並以 exit code 2 結束，而不是丟出 traceback。

## 專案結構

```
backend/        FastAPI 後端（app/api、services、gateway、simulator、ai、models、schemas）、alembic、tests、Dockerfile
frontend/       React + TypeScript + Vite 前端、src/test（vitest）、Dockerfile、nginx.conf
knowledge_base/ 營養種子知識庫（教學示範資料）
scripts/        demo_smoke.py（端到端 Demo 檢查）
docs/           規格文件、DEMO_GUIDE.md、DIAGRAMS.md、architecture.svg
docker-compose.yml  .env.example  .dockerignore
```
#   c o m m u n i t y - s m a r t - g r o c e r y - d e m o  
 