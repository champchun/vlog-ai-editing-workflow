# Media｜原始影片與照片

將專案原始影片與照片一起放在此資料夾，可依日期或活動建立子目錄。Stage 0A 遞迴掃描，依實際格式／媒體探測保存 `media_type=video/photo`，不得只由所在資料夾推斷類型。無法辨識的檔案需列入警告。

影片才有影片 duration、FPS、音軌與 cut range；照片可提供 EXIF、場景與靜態素材候選。Stage 0D 的 Source Video Clip Count 只計影片，照片另計。已確認代理檔與重複檔依既有規則排除。

正式分析、Storyboard 與 Render 依 JSON 的 `source_path` 回到原始素材。照片納入 Stage 1 時必須明訂 `media_type=photo` 與顯示時長。不得混入 review proxy、Storyboard 圖、cache 或成片。
