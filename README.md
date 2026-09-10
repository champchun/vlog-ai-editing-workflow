# Vlog AI 自動剪輯工作流

這個 repository 用來管理 AI 輔助家庭／旅遊 Vlog 的完整工作流、各階段 Prompt、腳本、規則、測試結果與相關資源。

核心流程：

Stage 0A Local Pre-analysis → Stage 0B AI Visual Review → Stage 0C Event Fusion & Validation → Stage 0D Master Footage Review → Stage 1 Story & Edit Decisions → Stage 1R Storyboard Review Gate → Stage 2 Rough Cut → Stage 3 Final Color & Mix

## 核心 Human Review Gate

- **Stage 0D = 防漏選**：所有原始影片都必須可快速檢視，AI 與 Human 各自留下候選判斷與理由。
- **Stage 1R Storyboard = 防選錯**：在 Render 前，用正式 cut range 從 Original Source 抽出的 Storyboard 驗證 AI 的剪輯選擇。

## 目錄原則

每個階段都有自己的目錄，除 `PROMPT.md` 與階段說明外，可自由放入該階段使用的 Python 腳本、JSON schema、範例輸出、測試資料、備註與工具設定。

`shared-resources/` 用來管理跨階段共用規則與資源說明；大型原始影片、Proxy、Render 成品不建議直接提交 GitHub，應以路徑／manifest 或外部儲存方式管理。
