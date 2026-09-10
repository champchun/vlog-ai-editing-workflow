# Stage 0B｜AI Visual Review

## 目的
對 Stage 0A 標記的重要、不確定或高故事價值區段進行真正的 Multimodal Vision 複核。

## 本目錄可放
- `PROMPT.md`
- Vision review 腳本或工具
- 抽幀規則
- 模型輸出 schema
- 錯誤案例與修正紀錄
- validation 範例

## 邊界
必須真正看像素；不得用 Transcript/GPS 偽造視覺結論。不做 Event Fusion 或剪輯決策。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0A 輸入：`process/workspace/project-output/stage0a_output/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0b_output/`
- 暫存抽幀/cache：`process/workspace/temp/`

照片與 GPS 只能輔助，不得取代影片像素複核；本階段的 visual semantics 必須有實際畫面證據。