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

## 記憶體限制建議
Stage 0B 透過 `resource_budget` 控制 VLM 負載。本專案使用 16 GB Mac + Ollama，預設配置為：

```json
{
  "memory_limit_gb": 8,
  "limit_mode": "advisory",
  "max_parallel_jobs": 1,
  "max_frames_per_request": 1,
  "max_image_edge_px": 720,
  "context_tokens": 2048,
  "checkpoint_every_regions": 1,
  "oom_retry_limit": 3
}
```

8 GB 是 VLM 工作負載的預算；`advisory` 表示不能保證瞬間用量永遠低於它。Prompt 不會自行改變 Mac 或 Ollama 設定。Agent 必須套用 runtime 參數，並在有可靠監控時停止超限後的新請求；没有監控時須明確記錄限制。

若使用 macOS Ollama App，先在終端機執行以下設定，再完全結束並重新開啟 Ollama：

```bash
launchctl setenv OLLAMA_NUM_PARALLEL 1
launchctl setenv OLLAMA_MAX_LOADED_MODELS 1
```

若使用終端機啟動 server，確認沒有另一個 Ollama server 後使用：

```bash
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

每個 API request 設定 `options.num_ctx=2048`。Stage 完成或資源阻擋時，使用 `ollama stop <本次模型名稱>` 卸載本次模型。參數與卸載方式參考 [Ollama 官方 FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)。模型載入已超過 8 GB 時，改用已獲准的較小量化 VLM；只減少影格無法保證足夠。

資源不足時先降低同時工作數、每批影格與圖片尺寸，再調低 batch/context 或使用已獲准的較小量化模型。每完成一個 region 就保存 checkpoint。降低資源只能改變分批方式，不能略過必要時間點；連續動作可拆成有重疊的小批次。超過重試次數仍失敗時應標 `RESOURCE_BLOCKED` 並讓 Stage 0B FAIL。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0A 輸入：`process/workspace/project-output/stage0a_output/`
- 原始影片：`process/workspace/media/`
- 原始照片：`process/workspace/media/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0b_output/`
- 暫存抽幀/cache：`process/workspace/temp/`

照片與 GPS 只能輔助，不得取代影片像素複核；本階段的 visual semantics 必須有實際畫面證據。

## 本機腳本（`scripts/`）
依序：`b1_plan.py`（取樣計畫）→ `b1b_densify.py`（長片加密）→ `b2_frames.py`（原片抽幀，硬體解碼、檢視用 LUT）→ `b3_vlm.py`（Ollama VLM，逐張 checkpoint）→ `b4_segments.py`（段落候選）→ `b5_select.py`（規則挑出要給 Agent 複核的項目）→ `b6_sheets.py`（聯絡表）→ Agent 複核 → `b7_assemble.py`（正式輸出與驗證）。VLM 執行期間不要同時跑其他 4K 解碼工作。
