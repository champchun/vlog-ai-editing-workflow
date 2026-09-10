# Stage 0D Master Footage Review Console - Reusable Kit

方法一：我為您打包的「通用腳本工具包」(最推薦、最穩定)
我已經幫您建立了一個名為 Reusable_Stage0D_Console_Kit 的資料夾。裡面包含了生成這個 Floating Player 主控台的所有通用程式碼與 HTML 模板。

下次開新專案時的操作步驟：

1. 將本資料夾內的內容複製到您的新 Vlog 專案目錄下（例如新建並放入 tools 資料夾內）。
2. 在新專案讓 AI 跑完前期的 Stage 0A ~ 0C（產生 metadata 與 AI 視覺摘要）。
3. 在新專案的根目錄開啟終端機，執行以下指令讓工具自動讀取新素材並產生對應的圖檔與清單：
```bash
python3 tools/build_stage0d.py
```
4. 跑完後啟動伺服器：
```bash
python3 tools/app.py
```
接著前往 http://localhost:8080，全新的審片主控台就準備好了！
