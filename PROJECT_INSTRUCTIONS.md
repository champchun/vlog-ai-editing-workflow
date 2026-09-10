# PROJECT_INSTRUCTIONS｜Vlog AI 自動剪輯工作流

本 repository 是一套家庭／旅行 Vlog 的 AI 協作剪輯工作流規格庫。它不是單一程式，而是由多個階段、Prompt、驗證規則、範例程式與資源檔組成。

## Repository 兩大區

### `review/`
給 ChatGPT / Reviewer 使用。負責驗收另一個 AI Agent 的 JSON、HTML、Storyboard、execution log、validation report 與影片技術結果，輸出 PASS / PASS_WITH_WARNINGS / FAIL，必要時產生 Correction Prompt。

### `process/`
給 AI Agent 實際執行工作流使用。所有 Stage Prompt、Stage README、共用資源與實際專案 workspace 都集中在這裡。

不要把 Reviewer 與 Process Agent 的角色混在一起。

## 新對話／新 Agent 的第一件事

如果你是第一次接手此專案，請先讀：

1. 根目錄 `README.md`
2. 本檔 `PROJECT_INSTRUCTIONS.md`
3. `process/README.md`
4. `process/WORKSPACE_RULES.md`
5. 目前要處理的 `process/stage-*/README.md` 與 `process/stage-*/PROMPT.md`
6. 若任務是驗收前一個 Agent 產出的 JSON/檔案，再讀 `review/VALIDATION_REVIEW_PROMPT.md`
7. 若該 Stage 目錄有 `examples/`、`assets/`、schema 或其他 README，將它們視為該階段可用參考與資源

不要依賴聊天記憶猜工作流規則；GitHub repository 才是規格來源。

## AI Agent Workspace

`process/workspace/` 是實際專案的 AI Agent 操作台：

- `process/workspace/videos/`：Original Video Media
- `process/workspace/photos/`：Original Photos
- `process/workspace/gps/`：GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV / 手動地點資料
- `process/workspace/project-output/`：各 Stage 正式輸出
- `process/workspace/temp/`：可重建的 proxy、frame cache、中間檔、臨時 logs

Stage 專屬資源不搬到 workspace。例如 Stage 3 的 BGM/LUT 留在 `process/stage-3-final-color-mix/assets/`。

## 標準流程

Stage 0A Local Pre-analysis
→ Stage 0B AI Visual Review
→ Stage 0C Event Fusion & Validation
→ Stage 0D Master Footage Review
→ Human Review Gate
→ Stage 1 Story & Edit Decisions
→ Stage 1R Storyboard Review Gate
→ Stage 2 Rough Cut
→ Stage 3 Final Color & Mix

## 各階段責任

### Stage 0A｜Local Pre-analysis
做客觀前處理：metadata、transcript、素材索引、技術資訊。不得做故事選片。

### Stage 0B｜AI Visual Review
真正看畫面做 visual semantics、人物／動物／物件／動作、畫質與 visual regions。不得讓 transcript 取代畫面判斷。

### Stage 0C｜Event Fusion & Validation
融合時間、畫面、對話、互動、反應、因果與必要 GPS 輔助，形成 Event candidates，並完成 Stage 0 validation。

### Stage 0D｜Master Footage Review
核心目的：**防漏選**。
所有原始影片都必須進入 Master Review，包括 AI 不推薦的素材。AI Review 與 Human Review 分開保存，Human 可標記 Candidate / Important / Must Keep / Skip 並寫理由。Stage 1 必須正式讀取 Human Review。

### Stage 1｜Story & Edit Decisions
真正做導演與剪輯決策。採 Coverage First：先保 major scenes，再決定 Event、Shot、Cut Point。不得用 transcript sentence + padding 直接當剪輯方法。

### Stage 1R｜Storyboard Review Gate
核心目的：**防選錯**。
Storyboard 必須從 Original Source、依 edit_decisions 的真實 cut range 抽 frame。Storyboard 是 Render 前固定 QA Gate。PASS 才能進 Stage 2；FAIL 回 Stage 1 修指定 Shot/Event。

### Stage 2｜Rough Cut
**Dumb Executor**。只照已核准 edit_decisions 執行 1080p Rough Cut。不得自行換鏡、刪鏡、重排、重新決定 story pacing。

### Stage 3｜Final Color & Mix
從 Original Source 重建核准 timeline，完成調色、shot matching、audio cleanup、BGM/ducking、必要包裝與 Final QC。不得用 rough cut 當 Final Source，不得重新做導演決策。

## 兩個 Human Gate

Stage 0D Master Footage Review = 防止 AI 漏選。

Stage 1R Storyboard Review = 防止 AI 選錯鏡頭／cut range。

這兩個 Gate 不可合併或省略。

## 驗收 Agent 產物的標準模式

當使用者把某 Stage Agent 產出的 JSON、validation report、HTML、執行 log 或其他檔案交給你時，不要直接憑印象評論。

請依序：

1. 判斷這是哪個 Stage 的產物。
2. 讀取對應 `process/stage-*/PROMPT.md`。
3. 讀取對應 Stage README。
4. 讀取 `review/VALIDATION_REVIEW_PROMPT.md`。
5. 若有上游 validation / 必要 input，一併檢查 `process/workspace/project-output/` 內相關資料。
6. 檢查 schema / 欄位完整性。
7. 檢查數值與引用範圍是否合法。
8. 檢查跨檔案一致性。
9. 檢查是否違反該 Stage 的責任邊界。
10. 檢查核心邏輯，而不是只看 JSON 能不能 parse。
11. 最後輸出 PASS / PASS_WITH_WARNINGS / FAIL。

若 FAIL，必須提供可直接貼回原 Agent 的 Correction Prompt，而不是只描述問題。

## PASS 定義

### PASS
必要規則與關鍵 validation 全部符合，可進下一 Stage。

### PASS_WITH_WARNINGS
沒有阻擋性錯誤，但存在非阻擋風險、可改善項目或精度不足。必須說明是否可進下一 Stage。

### FAIL
任何會造成錯誤選片、漏素材、錯 cut、錯 source、跨 Stage 越權、輸出缺漏、validation 不一致、hard unusable 被錯誤採用等重要問題。

FAIL 時不得假裝可繼續下一 Stage。

## Workspace 與 Source 規則

- 影片正式來源：`process/workspace/videos/`
- 照片：`process/workspace/photos/`，可作 EXIF/場景/Coverage/靜態素材候選，但不得假裝成影片
- GPS/Timeline：`process/workspace/gps/`，日期與時間是硬限制，地點不足時維持 unknown/approximate
- 正式輸出：`process/workspace/project-output/`
- 暫存：`process/workspace/temp/`，不得成為正式 Render Source

Review proxy、Storyboard JPG、Stage 0 sample frame、old rough cut、temp cache 都不得取代 Original Video。

## Stage 0D 範例程式

`process/stage-0D-master-footage-review/examples/` 內若有 `build_stage0d.py`、`app.py`、`master_footage_review.html` 等，應視為可重用 prototype / implementation reference。

正式規格仍以 `process/stage-0D-master-footage-review/PROMPT.md` 為準。若範例程式與 Prompt 不一致，修改或適配範例，不可反過來降低正式規格。

## Stage 3 既有資源

`process/stage-3-final-color-mix/assets/` 中已有可用 BGM 與 Technical LUT。

BGM 可依 Stage 3 Prompt 使用。

LUT 只能在素材 color profile 被可靠確認時套用：D-Log 對 D-Log LUT、D-Log2 對 D-Log2 LUT。`color_profile=unknown` 時不得套 LUT，也不得因為素材來自 DJI / OSMO Pocket 就猜 profile。

## 新對話最短啟動語句

### Reviewer 模式
「請先讀 `champchun/vlog-ai-editing-workflow` 的 `PROJECT_INSTRUCTIONS.md` 與 `review/VALIDATION_REVIEW_PROMPT.md`，再依 `process/` 中目前 Stage 的 Prompt 幫我驗收這次 Agent 產出的檔案。」

### Process Agent 模式
「請先讀 `PROJECT_INSTRUCTIONS.md`、`process/README.md`、`process/WORKSPACE_RULES.md` 與目前 Stage 的 README/PROMPT，依 `process/workspace/` 的素材與輸出結構執行。」

收到這類指示後，應先讀 repo 規格，再處理實際檔案，不要要求使用者重新解釋整套工作流。