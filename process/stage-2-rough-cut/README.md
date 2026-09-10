# Stage 2｜Rough Cut

## 目的
忠實執行 Stage 1 已核准的 edit decisions，輸出 1080p Rough Cut。

## 本目錄可放
- `PROMPT.md`
- FFmpeg / render scripts
- Reframe / audio execution tools
- Validation scripts
- Execution log schema
- Rough Cut 測試輸出說明

## 核心
Stage 2 = Dumb Executor。不得重新做任何 Story、Event、Shot 或 Cut 決策。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 1：`process/workspace/project-output/stage1_output/`
- Storyboard Gate：`process/workspace/project-output/stage1_review/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- 正式輸出：`process/workspace/project-output/stage2_output/`
- 暫存：`process/workspace/temp/`

正式影片 Shot 必須從 Original Video 執行。Storyboard JPG、Stage 0D proxy、temp proxy、舊 rough cut 都只能當參考，不能成為正式來源。