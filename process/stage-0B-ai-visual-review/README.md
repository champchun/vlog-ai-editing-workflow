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
Stage 0B 透過 `resource_budget` 控制 VLM 負載。RAM 較有限的 Mac 可先使用：

```json
{
  "memory_limit_gb": null,
  "limit_mode": "advisory",
  "max_parallel_jobs": 1,
  "max_frames_per_request": 6,
  "max_image_edge_px": 1280,
  "context_tokens": 4096,
  "checkpoint_every_regions": 1,
  "oom_retry_limit": 3
}
```

`memory_limit_gb=null` 代表目前沒有 runtime 可驗證的硬限制。若透過容器或 supervisor 確實限制記憶體，再填入實際 GB 並把 `limit_mode` 設為 `hard`。Ollama、llama.cpp 或其他 VLM 的 batch、GPU layers、量化與模型常駐參數依實際 runtime 設定，並記錄在 `stage0b_resource_log.json`；不要把未支援的參數寫成已生效。

資源不足時先降低同時工作數、每批影格與圖片尺寸，再調低 batch/context 或使用已獲准的較小量化模型。每完成一個 region 就保存 checkpoint。降低資源只能改變分批方式，不能略過必要時間點；連續動作可拆成有重疊的小批次。超過重試次數仍失敗時應標 `RESOURCE_BLOCKED` 並讓 Stage 0B FAIL。

## Repo 資料結構
執行前讀 `process/README.md` 與 `process/WORKSPACE_RULES.md`。
- Stage 0A 輸入：`process/workspace/project-output/stage0a_output/`
- 原始影片：`process/workspace/videos/`
- 原始照片：`process/workspace/photos/`
- GPS/Timeline：`process/workspace/gps/`
- 正式輸出：`process/workspace/project-output/stage0b_output/`
- 暫存抽幀/cache：`process/workspace/temp/`

照片與 GPS 只能輔助，不得取代影片像素複核；本階段的 visual semantics 必須有實際畫面證據。
