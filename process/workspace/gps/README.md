# GPS

放本專案 GPS / Google Maps Timeline / GPX / KML / GeoJSON / CSV / 手動地點資料。

規則：日期與時間是硬限制；GPS/Timeline 可協助具名地點與事件融合，但不得跨日期配對，也不得只靠 transcript/畫面語意猜景點。若證據不足，地點維持 `unknown` / `approximate`。


Google Timeline 新版匯出（`Timeline.json`）只含座標與 `placeID`，沒有地名。地名由使用者確認後存 `place_names.json`（`source=user_confirmed`，見 Stage 0C）。Timeline 與 `place_names.json` 屬私人位置資料，不要 commit。