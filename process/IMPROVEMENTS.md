# IMPROVEMENTS｜流程改進清單與邏輯漏洞

來源：Stage 0D → 3 第一次完整跑完（沖繩 2026-09-24～29）後的檢討。狀態欄：`TODO` 未做、`DONE` 已完成。

> **併入 master 時的校正（2026-10-27）：** 本清單最初寫於分支 `stage0-pipeline-and-spec-updates`，該分支的程式碼沒有併入 master（兩邊的 Stage 1／3 腳本衝突）。下列項目請以 master 現況為準：
> - **B-roll 標記與快速滑片手勢**：master 已有（`stage-0D-master-footage-review/scripts/app.py`、`quick_review.html`），且支援段落層級 `segment_reviews[].broll`，因此 C1、C2 在 0D 端已解決；仍待確認 Stage 1 是否讀取 `broll`。
> - **A1／A3（寫死 PASS、無範圍檢查）**：只在上述分支的 Stage 2／3 報告腳本修過，master 的腳本尚未檢查，狀態視為 TODO。
> - 其餘（Stage 1 事實由資料計算、重疊檢查、PASS 後變動需再確認、人工驗收點、交接摘要、地點卡規則與日期須用 `creation_time` UTC 而非檔名時間）皆 TODO。

## 一、該修正的步驟

| # | Stage | 項目 | 狀態 |
|---|---|---|---|
| 1 | 0D | B-roll 標記（`human_review.broll`）已做；Stage 1 要讀它，並規定 B-roll 取哪一段、多長、什麼速度 | 0D 標記 DONE（master 已有）／Stage 1 讀取待確認 |
| 2 | 1 | 天數、日期、地點由素材資料計算，不由 Agent 憑印象寫；片名由使用者確認後鎖定（本次誤寫「五天四夜」，實為六天五夜，`story_plan.json` 與 `build_stage1.py` 仍待改） | TODO |
| 3 | 1 | 驗證加入「同一支原片剪輯範圍重疊／間隔過近」檢查（本次 SH019/SH020 聲音重複由使用者聽出） | TODO |
| 4 | 1R | 帶標籤的串接審片影片列為標準輸出；鏡頭使用固定 ID（非順位編號）；只重建受影響鏡頭 | TODO（`make_review_cut.py` 已有） |
| 5 | 全部 | PASS 之後的任何變動必須列在報告並由使用者重新確認（本次 PASS 後曾自行把 B-roll 的 `audio_strategy` 由 ambient 改 mute） | TODO |
| 6 | 2 | 規格寫明 Stage 2 是否獨立人工驗收；否則 Stage 2 與 Stage 3 重複解碼 4K（約 5 分＋20 分） | TODO |
| 7 | 3 | 修快取鍵（tuple vs list，已修）、色彩測量加刻度範圍檢查（10-bit 為 0–1023，已修但無防呆）、音訊提供可抽聽依據 | 部分 DONE |
| 8 | 全部 | 每個 Stage 結束時產出交接摘要，新對話靠 repo 與摘要接手 | TODO |
| 9 | 全部 | 執行環境注意事項：路徑含撇號（`Neil's M2`）、macOS `sed -i` 行為、`ffmpeg` 濾鏡路徑跳脫 | TODO |

## 二、邏輯漏洞

### A. 報告比實際可靠（最嚴重，優先處理）
- **A1 寫死的 PASS。**（僅在舊分支修過，master 待查） Stage 3 報告中 `audio_cleanup`、`white_balance_qc`、`dialogue_leveling` 等直接 `chk(True, …)`，沒有任何東西在驗證；Stage 2 `audio_sync_check` 只比對長度，不是同步。「PASS」實際意思是「無解碼錯誤、長度與響度達標」，不代表品質合格。處理：改成真正檢查，或標 `NOT_VERIFIED`／`NOT_PERFORMED`，不得顯示 PASS。
- **A2 自己驗證自己。** Stage 1 驗證由產生決策的同一支腳本撰寫；Stage 1R `no_editorial_change` 以建立 Storyboard 的同一份檔案比對，必然 PASS。專案有獨立的 `review/` 驗收角色，本次流程未使用。處理：Gate 前一律交 `review/` 獨立驗收，或至少以獨立腳本重算。
- **A3 驗證沒有合理範圍檢查。**（僅在舊分支修過，master 待查） 色彩刻度寫錯（Y 值 0–1023 當 0–255）整個 Stage 3 仍 PASS。處理：所有量測值加 sanity bounds，超出即 FAIL。

### B. 關卡沒擋到該擋的
- **B1 使用者核准的不是最終成品。** 使用者核准的是 v9 審片版（無調色、無 BGM、無地點卡），Stage 3 才加上這些，之後無人工關卡，只有 Agent QC。處理：Stage 3 加一個人工驗收點。
- **B2 Stage 2 無人驗收，卻被假設已驗收。** Stage 3 Prompt 寫「Rough Cut 已經人工確認」，本次沒有。處理：規格明定；或讓 Stage 3 不依賴此假設。
- **B3 片長超標無關卡。** 參考 180–360 秒、成片 446 秒，僅有警告。處理：超標需使用者明確同意或指定縮減優先序。
- **B4 核准物件與最終決策不同。** 使用者核准的影片與其後 `edit_decisions` 雜湊不一致時，報告要保存「核准的是哪個影片、對應哪個雜湊」。

### C. B-roll 資料語意
- **C1 標記是整支素材，不是時間段。** 使用者標一支是 B-roll，Stage 1 仍須自行決定取哪一段。處理：允許段落層級標記（沿用 `segment_reviews`），或規格明定 Stage 1 取段規則。
- **C2 A-roll 與 B-roll 互斥，但長素材常兩者皆有。** 處理：支援同一支素材分段標記。
- **C3 右滑把 `status` 設為 `NO_PREFERENCE`。** Stage 1 對此狀態中性，被 AI 評為「可能略過」的素材仍可能被捨棄。處理：Stage 1 對 `broll=true` 設獨立候選池，不受 AI 評分過濾。

### D. 證據強度
- **D1 地點卡比證據更肯定。** 地點由 Stage 0C 以時間配對推得（例：Blue Seal 夾在 Neo Park 中、Zane濱 訪問時間窗跨前一晚），字卡把輔助證據變成斷言。處理：卡片證據欄記錄配對方式；弱配對者標 `needs_confirmation`。
- **D2 壓低 BGM 依賴 ASR 句界。** ASR 會把重複字辨識成長句（本次一句約 9 秒的「丟丟丟…」），導致音樂被壓太久。處理：用 VAD 交叉驗證，並限制單一語音窗最長值。
- **D3 欄位只在程式碼、不在規格。** `is_broll`、`timeline_duration`、`audio_strategy=mute` 於慢動作 B-roll 的用法由腳本產生，Stage 1/2/3 規格未定義。處理：補進 Stage 1 schema 與 Stage 2/3 Prompt。

## 三、建議順序
1. A1、A3：把寫死的 PASS 改成真檢查或 `NOT_VERIFIED`。
2. B1、B2：規格明定人工驗收點。
3. C1、C2、C3：B-roll 段落標記與 Stage 1 讀取。
4. 其餘依序。

## 四、備註
- 本檔只列問題與處理方向；尚未修改 Stage 2／3 的驗證腳本。
- 地點卡規則曾在舊分支改為「每次地點切換顯示」，規格尚未同步（Stage 3 Prompt 原寫「新主要 Scene 第一次出現」）；地點卡日期請用 `creation_time`（UTC）換算當地時間，不要用檔名時間。
