# Stage 1｜Story & Edit Decisions

## 目的
把 Stage 0 客觀素材理解與 Stage 0D Human Review 轉成真正的導演與剪輯決策。

## 本目錄可放
- `PROMPT.md`
- Scene inventory / story plan schema
- Cut review 工具
- `edit_decisions.json` 範例
- 驗證規則與案例

## 核心
Coverage First：先確保主要 Scene 都被代表，再做 Event / Shot / Cut 決策。Stage 1 不 Render。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0：`process/workspace/project-output/stage0c_output/`
- Stage 0D：`process/workspace/project-output/stage0d_master_review/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage1_output/`
- 暫存：`process/workspace/temp/`

影片 Shot 的 `source_path` 必須回到 Original Video；照片若被納入故事，需明確標示為 photo，不得偽裝成影片 Shot。