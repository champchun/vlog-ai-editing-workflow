# Stage 3｜Final Color & Mix

## 目的
從 Original Source 重新建立已核准 Timeline，完成 Final Color、Shot Matching、Audio Cleanup、BGM/Ducking、必要包裝與 Final QC，輸出 1080p Master。

## 本目錄可放
- `PROMPT.md`
- `assets/bgm/`：Stage 3 可用 BGM
- `assets/lut/`：Technical LUT
- Color / audio / BGM scripts
- LUT 與 color profile 規則說明
- Final QC checklist
- Execution log / validation schema
- 測試輸出與版本紀錄

## 本專案指定資源
### BGM
`assets/bgm/quirky_romcom_3_4_bgm.mp3`

此曲為目前工作流預設可用 BGM。實際使用區段由 Stage 3 依 Scene、Dialogue、Reaction 與節奏決定，不代表必須全片鋪滿。

### Technical LUT
`assets/lut/DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube`

僅用於已可靠確認為 D-Log2 的素材。

`assets/lut/DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube`

僅用於已可靠確認為 D-Log 的素材。

不可因素材來自 DJI 就自動套 LUT；`color_profile=unknown` 時不得使用上述 LUT。

## 核心
Stage 3 只做 finishing，不重新做導演或剪輯決策；Rough Cut 只能作 reference，不可成為 Final Source。
