# 圖表集

> 這些圖依**實際建置結果**繪製（模組名稱對應程式碼）。`docs/ARCHITECTURE.md` 是規格層級的設計圖；
> 兩者若有出入，以本文件與程式碼為準。Mermaid 圖可直接在 GitHub / GitLab / VS Code 預覽中顯示。

## 1. 實際建置架構

![實際建置架構](architecture.svg)

虛線 = 模擬的硬體／傳輸；實線 = 已實作的軟體；藍色 = AI 層（對交易資料唯讀）。

## 2. 16-byte 封包格式

欄位皆為大端序（big-endian）。實作在 `backend/app/gateway/packet.py`。

| 位元組 | 欄位 | 大小 | 說明 |
|---|---|---|---|
| 0–1 | Header | 2 | 固定 `AA 55` |
| 2–3 | Device ID | 2 | 對應 `devices.id` |
| 4–5 | Sequence | 2 | 防重放序號（uint16） |
| 6 | Command | 1 | `01` BIND_CARD · `02` ADD_ITEM · `03` REMOVE_ITEM · `04` CHECKOUT · `05` ALERT |
| 7–8 | Product code | 2 | 商品代碼 |
| 9–11 | Weight | 3 | 公克（uint24） |
| 12 | Flags | 1 | 目前必須為 0 |
| 13 | XOR | 1 | 位元組 0–12 的 XOR |
| 14–15 | Signature | 2 | 位元組 0–12 加示範金鑰的雜湊表簽章（**教學用，非密碼學安全**） |

範例（裝置 1、序號 1、ADD_ITEM、商品 101、320 公克）：

```
AA55 0001 0001 02 0065 000140 00 D9 847C
```

## 3. Gateway 驗證與購物車更新流程

每一種結果（含被拒絕的封包）都會寫入 `iot_events` 稽核表。圖中的狀態碼是 REST 回應的 HTTP 狀態；
被拒絕時回應本文仍包含每一步的驗證結果。

```mermaid
flowchart TD
    F["收到封包 frame"] --> L{"1. 剛好 16 bytes？"}
    L -- 否 --> R1["INVALID_LENGTH · 400"]
    L -- 是 --> H{"2. Header = AA 55？"}
    H -- 否 --> R2["INVALID_HEADER · 400"]
    H -- 是 --> C{"3-4. 指令受支援？<br/>ADD_ITEM / REMOVE_ITEM"}
    C -- 否 --> R3["UNSUPPORTED_COMMAND · 400"]
    C -- 是 --> K{"5. XOR 與雜湊表<br/>檢查碼相符？"}
    K -- 否 --> R4["CHECK_CODE_MISMATCH · 400"]
    K -- 是 --> D{"6a. 裝置已註冊？"}
    D -- 否 --> R5["UNKNOWN_DEVICE · 400"]
    D -- 是 --> S{"6b. 序號大於<br/>上次接受的序號？"}
    S -- 否 --> R6["SEQUENCE_REPLAY · 409"]
    S -- 是 --> X{"7. 欄位合規？<br/>商品>0、重量>0、flags=0"}
    X -- 否 --> R7["INVALID_FIELDS · 400"]
    X -- 是 --> U["消耗序號<br/>更新 last_sequence_number"]
    U --> M["轉成 NormalizedIoTEvent"]
    M --> CS{"購物車規則通過？<br/>商品、重量範圍、庫存、購物車狀態"}
    CS -- 否 --> R8["PRODUCT_NOT_FOUND 404<br/>WEIGHT_OUT_OF_RANGE 400<br/>INSUFFICIENT_STOCK / ITEM_NOT_IN_CART /<br/>REMOVE_EXCEEDS_CART 409<br/>購物車不變"]
    CS -- 是 --> OK["購物車更新 · 200"]
    R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 & OK --> AUD["寫入 iot_events 稽核"]
```

重點：Gateway 只要有任何一步失敗，序號就**不會**被消耗；通過全部 Gateway 檢查後即消耗序號，
即使購物車之後因業務規則拒絕。

## 4. 模擬結帳（單一資料庫交易）

```mermaid
sequenceDiagram
    actor R as 居民
    participant UI as Web UI
    participant API as FastAPI /checkout
    participant CS as checkout_service
    participant DB as PostgreSQL
    R->>UI: 選擇模擬付款結果並按下結帳
    UI->>API: POST /residents/{id}/checkout
    API->>CS: checkout(resident, SUCCESS 或 FAILURE)
    CS->>DB: 鎖定購物車列，再依 id 排序鎖定商品列
    alt 購物車為空 / 商品已下架 / 庫存不足
        CS-->>API: CheckoutRejected
        API-->>UI: 409 與原因（沒有寫入任何資料）
    else 模擬付款失敗
        CS->>DB: 建立 FAILED 訂單與明細快照 · COMMIT
        API-->>UI: 200 payment_status=FAILED（保留購物車、不扣庫存）
    else 模擬付款成功
        CS->>DB: 建立 PAID 訂單與明細快照
        CS->>DB: 扣庫存、刪除購物車項目 · COMMIT
        API-->>UI: 200 payment_status=PAID 與收據
        UI->>API: GET /products（刷新庫存）
    end
    Note over CS,DB: 任何錯誤都會讓整筆交易回滾
```

## 5. 營養助理流程

```mermaid
flowchart LR
    Q["問題 + 居民 id"] --> CTX["載入偏好、過敏原、<br/>最近付款成功的商品"]
    CTX --> G{"交易請求？<br/>結帳 / 改價格 / 改庫存"}
    G -- 是 --> REF["拒絕 · provider = guardrail<br/>不呼叫模型與工具"]
    G -- 否 --> T1["工具：get_inventory"]
    T1 --> T2["工具：get_product_info<br/>問題中提到的商品"]
    T2 --> REC["Recommender：<br/>依資料庫營養數據決定性排序"]
    REC --> T3["工具：search_nutrition_knowledge<br/>主題與商品片段"]
    T3 --> FACTS["已定案的事實<br/>無價格、無庫存、無姓名卡號"]
    FACTS --> P{"提供者"}
    P -- "mock（預設）" --> A1["範本答案"]
    P -- "anthropic（選用）" --> A2["LLM 措辭"]
    A2 -- "錯誤 / 逾時" --> A1
    A1 --> OUT["答案 + 來源（實際提供的知識 id）<br/>+ 推薦商品 + 工具呼叫紀錄"]
    A2 --> OUT
```

## 6. Docker Compose 拓樸

```mermaid
flowchart LR
    BR["瀏覽器"] -->|"http://localhost:5173"| FE
    BR -->|"REST http://localhost:8000"| BE
    subgraph compose["docker compose up --build"]
        FE["frontend<br/>nginx + 建置後的 React"]
        BE["backend<br/>FastAPI · alembic · seed"]
        DB[("db<br/>PostgreSQL 16<br/>volume: pgdata")]
    end
    BE -->|"db:5432"| DB
```

三個 port 都只綁定 `127.0.0.1`（示範用密碼、無管理員驗證，請勿對網路開放）。
瀏覽器直接呼叫後端，所以 `VITE_API_BASE_URL` 必須是**瀏覽器**連得到的網址。
