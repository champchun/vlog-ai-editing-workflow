# Process｜AI Agent 操作台

本目錄是 AI Agent 實際執行 Vlog 工作流的主要操作區。

## 資料結構

- `workspace/media/`：本專案原始影片與照片。遞迴掃描並以 `media_type=video/photo` 區分；正式剪輯與分析一律使用原始素材。照片可供 EXIF、場景與靜態素材候選使用。
- `workspace/gps/`：GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV / 手動地點資料。地點命名仍受日期、時間與可靠證據限制。
- `workspace/project-output/`：各 Stage 正式產物的集中工作區；各 Stage 應建立自己的子目錄，不要覆寫其他 Stage。
- `workspace/temp/`：可重建的暫存、frame cache、proxy、中間檔。不得把 temp 當正式來源。
- `shared-resources/`：跨 Stage 共用且非某單一 Stage 專屬的規則或工具。
- `stage-*`：各階段正式 `PROMPT.md`、README、examples、schema 或專屬 assets。

## 原則

1. Stage 專屬資源留在該 Stage，例如 Stage 3 的 BGM/LUT 留在 `stage-3-final-color-mix/assets/`。
2. `workspace/media/` 是原始專案素材；正式 Render 不得使用 review proxy、Storyboard JPG 或 temp cache 取代 Original Source。
3. GPS 是 auxiliary evidence，不可用語意猜測跨日期配對地點。
4. 每個 Stage 開始前先讀本檔、`WORKSPACE_RULES.md`、該 Stage 的 README 與 `PROMPT.md`。
5. 驗收工作由 repo 根目錄的 `review/` 負責；Process Agent 不得自行把 Human Gate 當成已通過。

## 階段預算關卡與對話切分
- 每個 Stage 開始前，先列出預估的 Claude token 範圍與選項；實際作業若會超出預估（新增複核回合、補聯絡表、重跑），先回報再繼續，不得自行加碼。
- 大量逐張／逐片的工作優先交給本機模型（例如 Ollama VLM、faster-whisper），Claude 只複核被規則挑出的項目；影像盡量留在本機。
- 建議每個 Stage 在新對話開始：規格與前階段成果都在 repo，不依賴聊天記憶；對話越長，每一步重送的 context 越貴。

## 地點命名
Timeline 匯出檔可能只有座標與 placeID、沒有名稱。Stage 0C 前須完成「地點命名」：由使用者逐地點確認，結果存 `workspace/gps/place_names.json`（`source=user_confirmed`）。見 Stage 0C 規格。
