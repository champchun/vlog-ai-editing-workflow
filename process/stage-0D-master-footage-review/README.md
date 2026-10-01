# Stage 0D｜Master Footage Review

## 目的
建立「全素材 AI × Human 審片介面」，讓所有原始影片（包含 AI 沒選的）都可快速預覽、比較 AI 理由與人工意見，避免漏選。

## 本目錄可放
- `PROMPT.md`
- `examples/`：可重用的 Stage 0D Prototype / Reference Kit
- Review Console（Python/HTML/JS）
- Proxy 建立工具
- Hero Frame / Contact Strip 規則
- Human Review schema
- `master_footage_review.json` 範例

## 核心
Stage 0D = 防漏選；Human Review 與 AI Review 必須分開保存，並交給 Stage 1 使用。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0 正式輸入：`process/workspace/project-output/stage0c_output/`
- 原始影片：`process/workspace/media/`
- 原始照片：`process/workspace/media/`（只作 context，不列入 Master Source Video Clip Count）
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0d_master_review/`
- 可重用範例：`process/stage-0D-master-footage-review/examples/`
- 暫存：`process/workspace/temp/`

Master Review 的基本單位是 `workspace/media/` 中的 Source Video Clip。Review proxy 只能審片，Stage 1/2/3 不得把 proxy 當正式來源。
全素材審片 HTML 強制使用台灣繁體中文（`zh-TW`），包含介面文字與每支影片的 AI 摘要、評價及推薦理由。JSON 欄位與狀態代碼保持原樣，原始逐字稿及人工輸入保留原文。通用 `review/` 驗收報告可使用英文；完整語言規則與驗收條件見 `PROMPT.md`。

人工操作分成「補充／修正摘要」與「選片意願」兩區。摘要操作顯示為「不修改、補充內容、修正錯誤、改寫摘要」；選片意願顯示為「尚未審查、不指定是否選用、列為候選、重要素材、必須再看、必須保留、略過」。介面使用繁中，JSON 仍保存 `NONE/APPEND/CORRECT/REPLACE` 與 `NOT_REVIEWED/NO_PREFERENCE/CANDIDATE/IMPORTANT/MUST_REVIEW/MUST_KEEP/SKIP`。只補充摘要時不得自動提高選片優先級。

## 實作紀錄（Stage 0D 首次執行）
本 repo 的實際執行腳本在 `scripts/`，取代範例中的 `build_stage0d.py`，改讀 Stage 0B/0C 實際 schema，且不讀任何 Stage 1 資料：

1. `d0_proxy.py`：建立 H.264/AAC 720p review proxy
2. `d1_build.py`：建立 `master_footage_review.json` 與影格清單
3. `d2_frames.py`：從原片抽 Hero／Contact／段落影格
4. `d3_finalize.py`：安裝 Console（`examples/app.py`、HTML）、寫 `proxy_manifest.json`、合併既有 Human Review
5. `d4_validate.py`：產生 `master_footage_review_validation.json`（含存檔／重啟保留測試，在暫存副本上跑，不污染真實 Human Review）

Console 啟動：`cd` 到 `workspace/project-output/stage0d_master_review/` 後執行 `python3 app.py`，開 http://127.0.0.1:8080。每次存檔會把 Human Review 合併進 `master_footage_review.json`（Stage 1 讀這份）。

### 規格未明訂、由實作決定的項目
- **AI 推薦計分門檻**：事件加權分 = 0.30 故事 + 0.20 情感 + 0.20 互動 + 0.15 畫面 + 0.15 新鮮；已確認精彩場景 +1.0、可靠逐字稿 +0.2、過場／零碎事件 −0.7、同事件 ≥4 支 −0.3、技術可用比例 <50% −0.5、片長 <4 秒 −0.3。≥3.0 強烈推薦、≥2.4 建議考慮、≥1.8 可選素材，其餘可能略過；`hard_unusable` 才標技術不合格。分數保存在 `ai_review.score`。
- **Proxy 來源**：由 Stage 0A 已驗證 1:1 的 LRF 轉成 H.264（直接從 4K 原片轉預估 1.5 小時以上，LRF 約 30 分鐘）。Proxy 僅供審片。
- **「時間 1:1」定義**：以時間長度差 ≤0.1 秒為準，不要求幀率相同。LRF 為 30fps，59.94fps 原片的 proxy 幀率較低，時間軸不變（`proxy_manifest.json` 的 `fps_note` 有標註）。
- **`review_relationship` 判定**：AI 的 `STRONG_CANDIDATE`／`CANDIDATE`／`OPTIONAL` 視為想留，`LIKELY_SKIP`／`TECHNICAL_REJECT` 視為略過。人工想留 + AI 想留 = `AGREE_KEEP`；想留 + AI 略過 = `AI_SKIP_HUMAN_KEEP`；人工略過 + AI 為強烈推薦／建議考慮 = `AI_KEEP_HUMAN_SKIP`；人工略過 + AI 為可選素材／略過 = `AGREE_SKIP`。沒有另設「混合」類型。段落標記另存 `segment_relationships`。
- **英文顯示處理**：上游少數英文術語（B-roll、Hero Scene、VLM、Agent 複核）在顯示層換成繁中；VLM 辨識的英文招牌／品牌文字保留原文，另列於 `signage_text_original`，不翻譯、不猜測。
