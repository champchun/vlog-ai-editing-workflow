# Stage 0A｜Local Pre-analysis

## 目的
建立客觀、可追溯的本機素材索引，整理 metadata、transcript、技術品質與待 AI Vision 複核區段。

## 本目錄可放
- `PROMPT.md`：正式 Agent Prompt
- Python / FFmpeg / ffprobe 工具腳本
- JSON schema
- 本機分析規則
- 測試輸出與 validation 範例
- 備註與除錯紀錄

## 邊界
不做 Story Planning、Event Selection、Shot Selection、Cut Point 或 Render。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- 原始影片：`process/workspace/media/`
- 原始照片：`process/workspace/media/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0a_output/`
- 暫存：`process/workspace/temp/`

Stage 0A 可讀照片 EXIF/GPS 作輔助，但不得把照片當影片；GPS/Timeline 僅作有時間約束的輔助證據。
## 本機腳本（`scripts/`）
依序執行（macOS；需 ffmpeg、exiftool、faster-whisper、OpenCV、Swift/Xcode CLT）：

```bash
cd process/stage-0A-local-pre-analysis/scripts
python3 s1_catalog.py      # metadata / color evidence / GPS provenance / LRF metadata pairing
python3 s3_transcribe.py   # Silero VAD + faster-whisper small，逐片快取於 temp/stage0a/transcripts/
python3 s2_visual.py       # 從原片依原生影格編號約 4fps 技術分析、抽樣影格
python3 s2c_proxy_check.py # LRF 內容與時間偏移驗證
python3 s2b_vision.py      # macOS Vision 候選標籤（人物/動物/物件/文字）
python3 s4_assemble.py     # 產出正式 stage0a_output 與 validation
```

中間快取在 `process/workspace/temp/stage0a/`（可刪除重建）；正式輸出在 `process/workspace/project-output/stage0a_output/`。各步驟以原片大小/mtime/參數做快取鍵，重跑只補算變更的片段。

## GPS 回寫（0A 之前，自行執行）
`scripts/geotag_engine.py` 依 `workspace/gps/` 的 Timeline 補寫沒有 GPS 的檔案（省略 `--timeline` 時，自動使用該資料夾內檔名含 `timeline` 的 .json；有多個會要求指定）（預設只預覽，加 `--write` 才寫入原始檔）。例：

```bash
python3 scripts/geotag_engine.py --timeline "../workspace/gps/Timeline 3.json" --media ../workspace/media/JPG
```

注意：報表預設寫在該素材資料夾的 `geotag_report.csv`；已回寫過的資料夾（例如 `DJI_001`）請勿再跑，否則報表會被「已有 GPS，略過」覆蓋，0A 就看不到原本的 Timeline 來源紀錄（需要重跑時加 `--report` 另存）。
