# Vlog AI 自動剪輯工作流

這個 repository 用來管理 AI 輔助家庭／旅遊 Vlog 的完整工作流、各階段 Prompt、腳本、規則、測試結果與相關資源。

核心流程：

Stage 0A Local Pre-analysis → Stage 0B AI Visual Review → Stage 0C Event Fusion & Validation → Stage 0D Master Footage Review → Stage 1 Story & Edit Decisions → Stage 1R Storyboard Review Gate → Stage 2 Rough Cut → Stage 3 Final Color & Mix

## 兩大工作區

### `review/`｜Reviewer 操作區
給 ChatGPT / Reviewer 驗收另一個 AI Agent 的產物。主要讀取 `review/VALIDATION_REVIEW_PROMPT.md`，依對應 Stage Prompt 做 PASS / PASS_WITH_WARNINGS / FAIL 與 Correction Prompt。

### `process/`｜AI Agent 操作台
給 AI Agent 真正執行各 Stage。所有 Stage README/PROMPT、Stage 專屬 examples/assets、共用資源與專案 workspace 都集中在這裡。

## AI Agent Workspace

`process/workspace/`：
- `videos/`：Original Video Media
- `photos/`：Original Photos
- `gps/`：GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV 等
- `project-output/`：各 Stage 正式輸出
- `temp/`：可重建暫存、proxy、frame cache、中間檔

詳細規則請讀 `process/WORKSPACE_RULES.md`。

Stage 專屬資源跟著 Stage 放，例如 Stage 3 的 BGM/LUT 保留在 `process/stage-3-final-color-mix/assets/`；Stage 0D 的可重用 Console 範例保留在 `process/stage-0D-master-footage-review/examples/`。

## 核心 Human Review Gate

- **Stage 0D = 防漏選**：所有原始影片都必須可快速檢視，AI 與 Human 各自留下候選判斷與理由。
- **Stage 1R Storyboard = 防選錯**：在 Render 前，用正式 cut range 從 Original Source 抽出的 Storyboard 驗證 AI 的剪輯選擇。

## macOS + Antigravity 本機剪輯工具層

本 repository 提供 `.agents/skills/local-editing-toolkit/SKILL.md`，讓 Antigravity 在執行 Stage 0A～3 時選用使用者合法取得並安裝於本機的轉錄、音訊、抽幀、渲染、字幕、圖卡與時間軸工具。

此 Skill 是橋接規則，不包含任何私人付費工具、音樂、音效或模板。正式導演決策仍以 Human Review、Stage Prompt、`story_plan.json`、`edit_decisions.json` 與對應核准雜湊為準；本機工具只能分析或執行，不得自行換鏡、改切點、重排或覆寫正式輸出。

### 1. 在 Mac 安裝私人功能 Skill

將私人 Skill 保留在 Antigravity 的全域個人目錄，不要複製或 commit 到本 repository：

```bash
mkdir -p "$HOME/.gemini/config/skills"
```

從使用者合法取得的私人技能包中，只複製需要的個別功能資料夾，並完整保留其 `SKILL.md`、`assets/`、`references/` 與必要資源。例如：

```bash
PRIVATE_SKILLS="/你的私人技能包路徑/skills"

cp -R "$PRIVATE_SKILLS/beat-cut-editor" "$HOME/.gemini/config/skills/"
cp -R "$PRIVATE_SKILLS/footage-sifter" "$HOME/.gemini/config/skills/"
cp -R "$PRIVATE_SKILLS/caption-doctor" "$HOME/.gemini/config/skills/"
cp -R "$PRIVATE_SKILLS/subtitle-translator" "$HOME/.gemini/config/skills/"
cp -R "$PRIVATE_SKILLS/broll-animation-studio" "$HOME/.gemini/config/skills/"
```

不要安裝任何統籌人格或針對其他 Agent 平台的 installer Skill。本工作流只按 capability 使用個別工具，避免工具統籌角色與 Stage Agent 搶奪決策權。

先確認 Mac 可找到基本執行環境：

```bash
python3 --version
ffmpeg -version
```

若個別功能還缺 Python/Node 套件或模型，先讓 Agent 列出缺項、影響與安裝範圍，再依使用者授權安裝；不得因讀到私人 Skill 的舊指令就自動修改全域環境。

### 2. 讓 Antigravity 載入專案 Skill

用 Antigravity 開啟本 repository 根目錄，重新開啟 Agent 對話。專案內應可使用：

```text
/local-editing-toolkit
```

私人功能 Skill 也會從 `~/.gemini/config/skills/` 被發現，但一般不要直接把整個剪片任務交給其中任一工具；由 `/local-editing-toolkit` 依目前 Stage 路由功能。

### 3. 放置專案素材

```text
process/workspace/videos/          Original Video Media
process/workspace/photos/          Original Photos
process/workspace/gps/             GPS / Timeline / 地點輔助資料
process/workspace/project-output/  各 Stage 正式輸出
process/workspace/temp/            可重建 proxy、frames、cache 與中間檔
```

Stage 3 專用 BGM、拍點 JSON 與 LUT 留在 `process/stage-3-final-color-mix/assets/`，不要搬進 workspace。

### 4. 執行 Stage

第一次可在 Antigravity 輸入：

```text
請使用 /local-editing-toolkit。

先讀 PROJECT_INSTRUCTIONS.md、process/README.md、
process/WORKSPACE_RULES.md，以及
process/stage-0A-local-pre-analysis/PROMPT.md，然後執行 Stage 0A。

可使用已安裝的本機工具做重複素材檢查、metadata、轉錄、
VAD、音訊體檢與抽幀，但必須轉成正式 Stage 0A schema，
保留原片時間戳與 provenance。不要啟動統籌人格，
也不要讓工具做故事選片。
```

Stage 0B 可輸入：

```text
請使用 /local-editing-toolkit，依
process/stage-0B-ai-visual-review/PROMPT.md 執行 Stage 0B。

先由 VLM 提出 Hero Scene 候選，再由你實際開啟候選的
連續影格或短片複核。不得只讀 VLM 摘要；分開保存
VLM nomination 與 agent_review。
```

後續依序執行 Stage 0C、0D、1、1R、2、3。Stage 0D 與 Stage 1R 完成後必須等待 Human Review PASS；工具成功執行不等於通過 Stage validation。

每一階段都可用以下開頭：

```text
請使用 /local-editing-toolkit，先讀取目前 Stage 的 Prompt，
只使用符合該階段責任的本機工具，並保存 adapter、執行與驗證紀錄。
```

### 5. 目前可直接使用與需要轉接的能力

可直接作為候選工具使用：完全重複素材檢查、音訊體檢、場景偵測、抽幀、字幕清洗、圖卡預覽與 BGM 拍點資料。

以下能力需要 Agent 先建立 adapter 並通過對應 Stage validation，不能直接把私人工具輸出當成正式結果：

- 私人逐字稿 JSON → Stage 0A transcript schema（含 VAD、uncertainty 與原片時間映射）
- 私人 EDL/renderer → 正式 `edit_decisions.json` 與 Stage 2 忠實執行規則
- 音訊檢查建議 → Stage 3 可追溯的處理與聽查紀錄
- Premiere / DaVinci Resolve / Final Cut Pro 時間軸 → 由核准決策產生的 handoff artifact

Stage 2 不得直接使用 schema 不相容的 renderer。非法切點、缺少音訊或不支援的指令必須阻擋並回報，不得自動夾短、跳過或靜默降級。

## 新對話

先讀 `PROJECT_INSTRUCTIONS.md`。

- 要驗收 Agent 產物：再讀 `review/VALIDATION_REVIEW_PROMPT.md`。
- 要讓 AI Agent 執行某 Stage：再讀 `process/README.md`、`process/WORKSPACE_RULES.md` 與對應 `process/stage-*/README.md` / `PROMPT.md`。

GitHub repository 是工作流規格來源，不要只依賴聊天記憶。
