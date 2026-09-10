# Vlog AI 自動剪輯工作流

這個 repository 用來管理 AI 輔助家庭／旅遊 Vlog 的完整工作流、各階段 Prompt、腳本、規則、測試結果與相關資源。

核心流程：

Stage 0A Local Pre-analysis → Stage 0B AI Visual Review → Stage 0C Event Fusion & Validation → Stage 0D Master Footage Review → Stage 1 Story & Edit Decisions → Stage 1R Storyboard Review Gate → Stage 2 Rough Cut → Stage 3 Final Color & Mix

## 兩大工作區

### `review/`｜Reviewer 操作區
給 ChatGPT / Reviewer 驗收另一個 AI Agent 的產物。主要讀取 `review/VALIDATION_REVIEW_PROMPT.md`，依對應 Stage Prompt 做 PASS / PASS_WITH_WARNINGS / FAIL 與 Correction Prompt。

### `process/`｜AI Agent 操作台
給 AI Agent 真正執行各 Stage。所有 Stage README/PROMPT、Stage 專屬 examples/assets、共用資源與專案 workspace 都集中在這裡。

## AI Agent Workspace

`process/workspace/`：
- `videos/`：Original Video Media
- `photos/`：Original Photos
- `gps/`：GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV 等
- `project-output/`：各 Stage 正式輸出
- `temp/`：可重建暫存、proxy、frame cache、中間檔

詳細規則請讀 `process/WORKSPACE_RULES.md`。

Stage 專屬資源跟著 Stage 放，例如 Stage 3 的 BGM/LUT 保留在 `process/stage-3-final-color-mix/assets/`；Stage 0D 的可重用 Console 範例保留在 `process/stage-0D-master-footage-review/examples/`。

## 核心 Human Review Gate

- **Stage 0D = 防漏選**：所有原始影片都必須可快速檢視，AI 與 Human 各自留下候選判斷與理由。
- **Stage 1R Storyboard = 防選錯**：在 Render 前，用正式 cut range 從 Original Source 抽出的 Storyboard 驗證 AI 的剪輯選擇。

## 新對話

先讀 `PROJECT_INSTRUCTIONS.md`。

- 要驗收 Agent 產物：再讀 `review/VALIDATION_REVIEW_PROMPT.md`。
- 要讓 AI Agent 執行某 Stage：再讀 `process/README.md`、`process/WORKSPACE_RULES.md` 與對應 `process/stage-*/README.md` / `PROMPT.md`。

GitHub repository 是工作流規格來源，不要只依賴聊天記憶。