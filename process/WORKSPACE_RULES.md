# WORKSPACE_RULES｜AI Agent 工作區規則

## 固定路徑

- `process/workspace/media/`：原始影片與照片，依 `media_type=video/photo` 區分
- `process/workspace/gps/`：GPS / Timeline / 地點資料
- `process/workspace/project-output/`：各 Stage 正式輸出
- `process/workspace/temp/`：可重建暫存

## 路徑責任

Stage 0A/0B/0C 應主動掃描 `media/`、`gps/` 中與本階段有關的資料。Stage 0D、1、1R、2、3 主要讀取上游正式輸出與 Original Media；需要照片/GPS 時仍回到 workspace 查詢。

## 混合素材與舊專案遷移

Stage 0A 遞迴掃描 media，以格式與媒體探測確認 `media_type=video/photo` 並保存原始 `source_path`。影片與照片分別計數，照片不得納入 Source Video Clip Count。Stage 0D 仍須列出所有原始影片；Stage 1 明訂照片顯示時長，Stage 2/3 按 media_type 執行。

舊專案仍有有效 source_path 時可繼續讀取。搬入 media 前先檢查同名衝突，不得覆蓋；以原檔雜湊建立舊／新路徑映射。更新引用的 JSON 後須重新計算內容雜湊並重驗受影響的 validation／Human Gate，不能沿用舊 PASS。若來源無法可靠對應，停止並回報，禁止只按檔名猜測。

正式輸出建議：
- `project-output/stage0a_output/`
- `project-output/stage0b_output/`
- `project-output/stage0c_output/`
- `project-output/stage0d_master_review/`
- `project-output/stage1_output/`
- `project-output/stage1_review/`
- `project-output/stage2_output/`
- `project-output/stage3_output/`

## 時間基準

拍攝時間與 GPS/地點配對一律以影片 `creation_time`（UTC）為準，顯示給使用者時，轉成 GPS 位置所在地的當地時間（例如設備時間為台灣、但 GPS 在日本，就顯示日本時間），不固定用台灣時間；當地時區取自 Timeline 該時段的時區偏移。檔名時間與容器 timecode 不可靠（DJI Osmo Pocket 4P 曾出現檔名晚 1 小時、timecode 差 0–4 小時），只作警告與交叉檢查。

## 禁止

- 不要把 Original Media 搬進 temp。
- 不要用 proxy / storyboard frame / old rough cut 當正式 Render Source。
- 不要把 Stage 3 專屬 BGM/LUT 搬到 workspace；它們留在 `process/stage-3-final-color-mix/assets/`。
- 不要把 GPS 的模糊語意配對當具名地點證據。
- 不要覆寫其他 Stage 的正式輸出；需要修正時保留版本或依 Stage 規則更新。
