# Review｜Validation Reviewer

這個目錄專門放「驗收其他 Agent 產物」的規格，屬於 Reviewer 操作區；不負責直接執行剪輯流程。

## 主要檔案
- `VALIDATION_REVIEW_PROMPT.md`：當某一 Stage Agent 產出 JSON、HTML、validation report、execution log 或其他檔案後，使用這份 Prompt 做獨立驗收。

## 使用方式
新的 ChatGPT / Reviewer 應先讀：
1. 根目錄 `PROJECT_INSTRUCTIONS.md`
2. `process/README.md` 與 `process/WORKSPACE_RULES.md`
3. 對應 Stage 的 `process/stage-*/README.md`
4. 對應 Stage 的 `process/stage-*/PROMPT.md`
5. 本目錄 `VALIDATION_REVIEW_PROMPT.md`
6. 使用者提供或 `process/workspace/project-output/` 中的實際產物

Reviewer 的工作不是重做整個 Stage，而是判斷是否符合正式規格、指出證據、給 PASS / PASS_WITH_WARNINGS / FAIL，並在 FAIL 時提供可直接回貼給產出 Agent 的 Correction Prompt。

## Reviewer 不應使用的來源
- 不要把 `process/workspace/temp/` 的暫存結果當正式產物
- 不要把 Stage 0D proxy、Storyboard JPG 或 rough cut 當 Original Source
- 驗收影片 source 時，正式 Original Video 位於 `process/workspace/videos/`
- GPS/照片若涉及驗收，分別讀 `process/workspace/gps/` 與 `process/workspace/photos/`，並遵守對應 Stage Prompt 的證據限制