# Shared Resources｜共用資源

這個目錄放跨階段共用的規則、schema、工具與資源說明。

建議可放：
- Original Media 路徑／manifest（不建議直接提交大型原始影片）
- BGM / LUT / GPS / Timeline 使用規則
- 共用 JSON schema
- FFmpeg helper scripts
- 檔名與版本規則
- QA / validation 共用函式
- 測試素材說明

## 重要原則
- Proxy、Rough Cut、Storyboard Frame 都不能取代 Original Source 作為 Stage 2 / Stage 3 正式來源。
- 具名地點需有可靠 GPS/Timeline、使用者確認或畫面可讀文字證據。
- ffprobe 的 bt709 tag 不等於已確認 Rec.709 profile。
- 大型媒體檔與 Render 成品建議放外部儲存，GitHub 只保存程式、Prompt、schema、manifest 與文件。
