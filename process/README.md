# Process｜AI Agent 操作台

本目錄是 AI Agent 實際執行 Vlog 工作流的主要操作區。

## 資料結構

- `workspace/videos/`：本專案原始影片。正式剪輯與分析一律以此處 Original Media 為來源。
- `workspace/photos/`：本專案原始照片。可供 EXIF/時間、場景理解、Coverage、Montage/Insert 候選使用；不得把照片誤當影片。
- `workspace/gps/`：GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV / 手動地點資料。地點命名仍受日期、時間與可靠證據限制。
- `workspace/project-output/`：各 Stage 正式產物的集中工作區；各 Stage 應建立自己的子目錄，不要覆寫其他 Stage。
- `workspace/temp/`：可重建的暫存、frame cache、proxy、中間檔。不得把 temp 當正式來源。
- `shared-resources/`：跨 Stage 共用且非某單一 Stage 專屬的規則或工具。
- `stage-*`：各階段正式 `PROMPT.md`、README、examples、schema 或專屬 assets。

## 原則

1. Stage 專屬資源留在該 Stage，例如 Stage 3 的 BGM/LUT 留在 `stage-3-final-color-mix/assets/`。
2. `workspace/videos/` 與 `workspace/photos/` 是原始專案素材；正式 Render 不得使用 review proxy、Storyboard JPG 或 temp cache 取代 Original Source。
3. GPS 是 auxiliary evidence，不可用語意猜測跨日期配對地點。
4. 每個 Stage 開始前先讀本檔、`WORKSPACE_RULES.md`、該 Stage 的 README 與 `PROMPT.md`。
5. 驗收工作由 repo 根目錄的 `review/` 負責；Process Agent 不得自行把 Human Gate 當成已通過。
