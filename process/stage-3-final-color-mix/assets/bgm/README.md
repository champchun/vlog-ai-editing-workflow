# BGM

本目錄放置 Stage 3 正式可用配樂。

目前指定檔案：
`2026-09-13_06_01_09.wav`

Stage 3 應優先評估此曲，並依 Scene、Dialogue、Reaction 與節奏安排實際使用區段與 ducking；不代表全片持續播放。

## 可重用拍點分析
`2026-09-13_06_01_09.beats.json`：包含原曲時間的拍點、BPM、相對 RMS 能量區段、音檔 SHA-256、工具版本與參數。由獨立的 `analyze_bgm.py` 產生，不需每次剪片重算；音檔內容或分析方法改變才重建。

在 repo 根目錄執行（需要 librosa、numpy、soundfile）：
```powershell
python process/stage-3-final-color-mix/assets/bgm/analyze_bgm.py process/stage-3-final-color-mix/assets/bgm/2026-09-13_06_01_09.wav
```

Stage 1 可據此規劃選配卡點過場；Stage 1R 聽查預覽；Stage 2 保留核准時間軸；Stage 3 依規劃混音。歌曲拍點需依所選音樂 source_start 與成片 timeline_start 換算，不能直接當影片切點。分析未經聽查，不能視為精準重拍、主副歌或情緒判定；人物互動完整性始終優先。

本次音檔長度 139.72 秒，自動估計約 129.20 BPM、279 個拍點；仍須對實際選用區段聽查。若 Windows 出現 LLVM `__svml_cosf8_ha` 錯誤，可在該次 PowerShell 工作階段設定 `$env:NUMBA_DISABLE_INTEL_SVML = '1'`，並將 `$env:NUMBA_CACHE_DIR` 指到新的可寫入暫存資料夾後重跑，避免重用不相容快取。
