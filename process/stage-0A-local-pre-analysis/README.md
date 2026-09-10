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
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0a_output/`
- 暫存：`process/workspace/temp/`

Stage 0A 可讀照片 EXIF/GPS 作輔助，但不得把照片當影片；GPS/Timeline 僅作有時間約束的輔助證據。