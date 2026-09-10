# Stage 1R｜Storyboard Review Gate

## 目的
把 Stage 1 已核准的 edit decisions 轉成真實影格 Storyboard，讓人類在 Render 前檢查是否選錯 Shot、Reaction、場景或 Cut 邊界。

## 本目錄可放
- `PROMPT.md`
- Storyboard 產生腳本
- Frame extraction / contact strip 工具
- Human review schema
- QA checklist 與錯誤案例

## 核心
Stage 1R = 防選錯。FAIL 時回 Stage 1 修正，Stage 1R 本身不得修改 edit decisions。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 1：`process/workspace/project-output/stage1_output/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- 正式輸出：`process/workspace/project-output/stage1_review/storyboard/`
- 暫存：`process/workspace/temp/`

Storyboard 的影片影格必須從 Original Video 的 approved cut range 抽取；Human PASS/FAIL 要保存到正式 `stage1_review/`，不得只存在 UI 暫存。