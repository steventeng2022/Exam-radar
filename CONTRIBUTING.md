# 參與貢獻 / Contributing

**繁體中文** | [English](CONTRIBUTING.en.md)

歡迎透過 [Issues](https://github.com/steventeng2022/Exam-radar/issues) 回報問題、提出建議，或提交 Pull Request。討論可使用繁體中文或英文，請尊重其他參與者。

## 開發與驗證

環境需求與啟動步驟見 [README](README.md#本地啟動)：Python 3.12+、Node.js 22+。先 fork 此專案並 clone 自己的 fork，建立修改分支；Python 使用虛擬環境並安裝根目錄的 requirements.txt，前端在 frontend/ 執行 npm install。

依修改範圍執行檢查，與 GitHub Actions 保持一致：

```bash
# repository 根目錄：後端與爬蟲
python -m pytest tests -q
python -m compileall -q backend crawler

# 前端
cd frontend
npm run typecheck
npm run build
```

測試使用本地 fixture，不需要真實校網或模型 API key。若修改行為，請補上能重現問題的測試；文件修正不需新增測試。

## 回報問題與提交 PR

- 回報問題時附上重現步驟、預期與實際結果、環境及已移除敏感資料的錯誤訊息。
- PR 請聚焦一個主題，說明修改原因、行為變化及實際執行的檢查。
- 若變更影響設定、API 或使用方式，請同步更新相關文件。
- 新增依賴時請註明授權條款，保留第三方版權與授權聲明。

## 資料與憑證

勿提交 .env、真實 token、資料庫、爬取文件或學生個資；設定範例請使用佔位值。測試資料請使用自行撰寫且可公開分享的內容。爬蟲修改仍需遵守 robots.txt、限速、來源核對及人工審核流程。

## 貢獻授權

提交內容前，請確認你有權提供該內容。除非另有明確說明並經維護者同意，你提交的原創貢獻採用本專案的 [MIT License](LICENSE)。第三方依賴和校方公告保留各自的權利；詳見 [README 授權說明](README.md#授權)。
