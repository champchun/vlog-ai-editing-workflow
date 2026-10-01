# Stage 0C｜Event Fusion & Validation

## 目的
把 Stage 0A/0B 的 metadata、transcript、visual review 與可靠 GPS/Timeline 融合成正式 Stage 0 Event 層。

## 本目錄可放
- `PROMPT.md`
- Event schema / fusion rules
- GPS/Timeline mapping 工具
- Validation scripts
- 測試案例與錯誤紀錄

## 邊界
建立 Event，但不做 Story Planning、Scene Coverage、Event Selection、Shot Selection 或 Render。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0A：`process/workspace/project-output/stage0a_output/`
- Stage 0B：`process/workspace/project-output/stage0b_output/`
- 原始影片：`process/workspace/media/`
- 原始照片：`process/workspace/media/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0c_output/`
- 暫存：`process/workspace/temp/`

GPS/Timeline 是本階段重要輔助資料，但具名地點仍必須通過同日/時間與可靠證據限制；照片與 GPS 的 provenance 必須和影片視覺證據分開。

## 本機腳本（`scripts/`）
`c1_group.py`（確定性分組）→ `c2_digest.py`（證據摘要）→ Agent 撰寫 Event → `c3_assemble.py`（正式輸出與驗證）→ `c4_places.py`（地點命名表，輸出 `workspace/gps/place_naming.html`；使用者填完下載 `place_names.json` 後重跑 `c3_assemble.py`）。
