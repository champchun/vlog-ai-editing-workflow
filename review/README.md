# Review｜Validation Reviewer

這個目錄專門放「驗收其他 Agent 產物」的規格。

## 主要檔案
- `VALIDATION_REVIEW_PROMPT.md`：當某一 Stage Agent 產出 JSON、HTML、validation report、execution log 或其他檔案後，使用這份 Prompt 做獨立驗收。

## 使用方式
新的 ChatGPT / AI Agent 應先讀：
1. 根目錄 `PROJECT_INSTRUCTIONS.md`
2. 對應 Stage 的 `PROMPT.md`
3. 本目錄 `VALIDATION_REVIEW_PROMPT.md`
4. 使用者提供的實際產物

Reviewer 的工作不是重做整個 Stage，而是判斷是否符合正式規格、指出證據、給 PASS / PASS_WITH_WARNINGS / FAIL，並在 FAIL 時提供可直接回貼給產出 Agent 的 Correction Prompt。
