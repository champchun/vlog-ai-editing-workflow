# Stage 0D｜Master Footage Review

## 目的
建立「全素材 AI × Human 審片介面」，讓所有原始影片（包含 AI 沒選的）都可快速預覽、比較 AI 理由與人工意見，避免漏選。

## 本目錄可放
- `PROMPT.md`
- `examples/`：可重用的 Stage 0D Prototype / Reference Kit
- Review Console（Python/HTML/JS）
- Proxy 建立工具
- Hero Frame / Contact Strip 規則
- Human Review schema
- `master_footage_review.json` 範例

## 核心
Stage 0D = 防漏選；Human Review 與 AI Review 必須分開保存，並交給 Stage 1 使用。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0 正式輸入：`process/workspace/project-output/stage0c_output/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`（只作 context，不列入 Master Source Video Clip Count）
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0d_master_review/`
- 可重用範例：`process/stage-0D-master-footage-review/examples/`
- 暫存：`process/workspace/temp/`

Master Review 的基本單位是 `workspace/videos/` 中的 Source Video Clip。Review proxy 只能審片，Stage 1/2/3 不得把 proxy 當正式來源。