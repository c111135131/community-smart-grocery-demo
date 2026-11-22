# Software Requirements Specification (SRS)

## 1. Project overview

### 1.1 Name
Community Smart Grocery — 基於 Matter over Thread 與輕量級防偽封包之社區無人健康生鮮超市系統。

### 1.2 Purpose
建立一個社區型無人健康生鮮超市概念驗證系統。居民可透過識別卡登入、依重量選購散裝生鮮、查看購物車與模擬結帳，並取得根據健康偏好與商品營養資料產生的飲食建議。

### 1.3 Educational objectives
- 理解 IoT 裝置事件如何經由通訊層送至 Gateway。
- 理解 Matter over Thread 在系統中的角色；以軟體模擬展示資料流。
- 設計並實作固定 16-byte 自訂二進位封包。
- 實作封包解析、基本完整性檢查與 Sequence Number 重放檢查。
- 使用 HTTP REST 串接前端與後端。
- 整合資料庫、交易流程與 AI 智慧服務。
- 理解 MCP、RAG、LLM Agent 的分工。

## 2. Users and roles

### 2.1 Resident
- 使用社區識別卡 ID 登入。
- 查看自己的基本健康偏好設定。
- 瀏覽商品及價格。
- 模擬將商品加入或移出購物車。
- 查看購物車小計與總額。
- 模擬付款。
- 查看購物後營養摘要與推薦。

### 2.2 Administrator
- 查看商品與庫存。
- 新增、修改商品資料（課堂 demo 可先提供 seed data，管理 CRUD 可列為次要功能）。
- 查看訂單。
- 管理員在 Phase 1 代表農民維護商品資料與庫存。

## 3. Main use case

1. 居民輸入識別卡 ID。
2. 系統讀取居民基本資料與健康偏好。
3. 居民選擇商品，例如番茄。
4. IoT Simulator 產生商品代碼、重量與序號等事件。
5. Simulator 將事件編碼為 16-byte packet。
6. Gateway 解析封包並檢查 Header、Command、Sequence Number、Check Code。
7. 通過驗證後，後端才更新購物車。
8. 後端依商品單價與重量計算價格。
9. 居民可移除商品或調整重量。
10. 居民進行模擬付款。
11. 系統建立訂單並顯示營養摘要。
12. AI 服務根據居民偏好、已購商品與營養知識提供建議。

## 4. Functional requirements

### FR-01 Resident card login
- 使用 seeded `card_id` 登入。
- 登入成功後回傳 resident profile。
- 不實作真實 NFC 讀卡；以輸入卡號模擬。

### FR-02 Product browsing
- 顯示商品名稱、分類、單位、每公斤價格、庫存重量及營養摘要。
- 商品價格由後端資料庫提供。

### FR-03 IoT event simulation
- 可選擇商品並輸入重量，產生 `ADD_ITEM` 或 `REMOVE_ITEM` 事件。
- 事件必須經過自訂 16-byte packet encode/decode。
- Simulator 應能展示原始封包 hex。

### FR-04 Gateway validation
- 檢查封包長度必須為 16 bytes。
- 檢查 Header。
- 檢查 Command 是否支援。
- 檢查 Sequence Number 是否為該 Device ID 的新序號。
- 檢查 Check Code。
- 驗證失敗不得更新購物車。

### FR-05 Cart
- 只接受 Gateway 驗證通過的 IoT event。
- 以商品代碼及重量維護購物車項目。
- 價格由後端計算，不信任前端或 AI 傳入的價格。
- 支援增加與移除商品。

### FR-06 Checkout
- 計算購物車總額。
- 提供模擬付款成功或失敗。
- 成功後建立訂單、訂單明細並更新庫存。
- 失敗時不得建立已付款訂單；購物車保留供重試。

### FR-07 Nutrition assistant
- 使用者可要求營養建議。
- AI 服務可取得居民健康偏好、商品資訊、訂單摘要及營養知識。
- 預設提供 mock AI provider，確保沒有 API Key 也能展示。
- AI 不得決定商品價格、重量、庫存或付款結果。

### FR-08 Administrator
- 可查看商品、庫存與訂單。
- 初期可使用 seed data，管理 CRUD 非第一優先。

## 5. Non-functional requirements
- 本專題以可理解、可展示、可測試為優先。
- 前後端以 HTTP REST API 溝通。
- IoT packet parser 與 gateway validator 必須可獨立測試。
- 關鍵商業邏輯需有單元測試。
- 提供 Docker Compose 啟動方式。
- 不將 demo 身分驗證、封包檢查或付款描述為 production-grade security。

## 6. Out of scope
- 真實金流。
- 真正的 NFC / RFID 硬體讀取。
- 真正的 HX711 電子秤驅動。
- 真正的 Matter commissioning、Thread Mesh 與 Border Router 部署。
- 生產級密碼學金鑰管理。
- 醫療診斷、疾病治療或專業營養師替代服務。
- 大規模併發、跨店庫存同步與正式營運監控。

## 7. Demo acceptance criteria
- 可用指定卡號登入。
- 可瀏覽至少 5 種 seeded 商品。
- 可產生 16-byte packet 並顯示 hex。
- 正確封包可通過驗證；錯誤封包與重複序號會被拒絕。
- 通過驗證的事件能更新購物車。
- 購物車價格由後端計算。
- 可完成模擬付款並產生訂單。
- 可顯示一段基於健康偏好與營養資料的建議。
- 可依文件啟動與操作 demo。
