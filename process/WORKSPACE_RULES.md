# WORKSPACE_RULES｜AI Agent 工作區規則

## 固定路徑

- `process/workspace/videos/`：原始影片
- `process/workspace/photos/`：原始照片
- `process/workspace/gps/`：GPS / Timeline / 地點資料
- `process/workspace/project-output/`：各 Stage 正式輸出
- `process/workspace/temp/`：可重建暫存

## 路徑責任

Stage 0A/0B/0C 應主動掃描 `videos/`、`photos/`、`gps/` 中與本階段有關的資料。Stage 0D、1、1R、2、3 主要讀取上游正式輸出與 Original Media；需要照片/GPS 時仍回到 workspace 查詢。

正式輸出建議：
- `project-output/stage0a_output/`
- `project-output/stage0b_output/`
- `project-output/stage0c_output/`
- `project-output/stage0d_master_review/`
- `project-output/stage1_output/`
- `project-output/stage1_review/`
- `project-output/stage2_output/`
- `project-output/stage3_output/`

## 禁止

- 不要把 Original Media 搬進 temp。
- 不要用 proxy / storyboard frame / old rough cut 當正式 Render Source。
- 不要把 Stage 3 專屬 BGM/LUT 搬到 workspace；它們留在 `process/stage-3-final-color-mix/assets/`。
- 不要把 GPS 的模糊語意配對當具名地點證據。
- 不要覆寫其他 Stage 的正式輸出；需要修正時保留版本或依 Stage 規則更新。
