# Stage 3 Assets

本目錄集中放置 Stage 3 Final Color & Mix 的正式可用資源。

## BGM
目標檔案：

`bgm/quirky_romcom_3_4_bgm.mp3`

用途：家庭／旅行 Vlog 的預設可用 BGM。Stage 3 依 Story Section、Dialogue、Reaction 與節奏決定實際使用區段與 ducking。

## LUT
目標檔案：

`lut/DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube`

只可套用於已可靠確認為 D-Log2 的素材。

`lut/DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube`

只可套用於已可靠確認為 D-Log 的素材。

## Safety
- LUT 是 Technical Conversion Resource，不是 Creative Look。
- 不得因為是 DJI / OSMO Pocket 素材就直接套用。
- 不得依 LUT 檔名反推 source profile。
- `color_profile=unknown` 時兩個 LUT 都不得使用。
- Execution Log 必須記錄 LUT filename、source clip、confirmed profile 與 profile evidence。
