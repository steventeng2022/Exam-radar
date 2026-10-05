# Exam Radar 📡

全台校園考試資訊搜尋引擎：搜尋各校公開段考範圍、比較進度、追溯原始公告與修正版。

參考 [STA](https://sta-tw.org/) 與 [STA monorepo](https://github.com/sta-tw/sta-tw.org) 的產品與前後端分工，獨立實作 Next.js + FastAPI + Python crawler。此專案不隸屬 STA 或任何學校。

## 本版能做什麼

- 繁體中文響應式網站：搜尋、年級／縣市／科目篩選、公告範圍比較、資料來源與版本紀錄。
- FastAPI 公開查詢 API；管理員 Bearer token 保護的抓取工作與審核 API。
- 校網優先級探索、robots.txt、限速、重試、公開網域與 IP 驗證、文件大小限制。
- HTML／PDF／DOCX／XLSX 解析；內容雜湊、条件式 HTTP、可恢復的持久化 frontier。
- 保守的規則抽取與校名核對；抽取結果進人工審核，通過後才公開。
- SQLite 本地開發、PostgreSQL 部署、Docker Compose 與 GitHub Actions 檢查。

**展示資料不是官方公告。** Demo 模式包含 5 所學校、3 個年級的虛構範圍與日期，僅供測試互動，禁止用於正式備考。Demo 學校停用爬取。正式模式預設空資料，不會暗中顯示假情報。

## 本地啟動

需求：Python 3.12+、Node.js 22+。從 repository 根目錄執行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DEMO_MODE=true ADMIN_TOKEN=local-development-token uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另開終端機：

```bash
cd frontend
npm install
npm run dev
```

開啟 http://localhost:3000 ，API 文件位於 http://localhost:8000/docs 。`/compare` 是比較介面，`/dashboard` 是控制台，`/crawler` 說明蒐集政策。控制台使用啟動後端時設定的 `ADMIN_TOKEN`，只存頁面記憶體。正式環境換成長隨機 token，不使用範例字串。

前端 API 位址可用 `frontend/.env.local` 設定：

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

這是公開的後端位址，不可放入 token。正式 Next.js build 時需設定正確值。`CORS_ORIGINS` 是逗號分隔的允許前端 origin，預設 `http://localhost:3000`。

## 抓取與資料審核

直接抓取單一已授權的官方校網，結果為 JSON，**此命令不直接發布資料**：

```bash
python -m crawler https://your-school.edu.tw --name '學校完整名稱' --id school-id --max-pages 40 --state data/frontier.sqlite3
```

先建立 `data/`。網站必須公開、允許 robots 索引，且來源校名能核對。跨網域附件需由管理者明確加入學校 domains，不能自動信任外部連結。AI provider 預設停用，不需 OpenAI API key，不會把校方文件送往外部模型。

持久化 worker 透過 `python -m backend.worker` 執行管理 API 排入的工作；registry 匯入與排程命令見 [backend/README.md](backend/README.md)。執行 worker 前先啟動 API，讓資料表完成初始化。worker 與 API 必須使用相同 `DATABASE_URL`。同一資料庫只啟動一個 worker，避免重複處理；新版以全域 lease 阻止第二個 worker 同時執行；仍只支援一個活躍 worker。

爬取採保守規則抽取：同校名、學年度、學期、次數、單一年級與科目範圍能確認時產生待審核版本。日期不明保留空值。多個年級混合表格、掃描 PDF 等情況可能只保存文件而無抽取結果；不猜測學校或範圍。

詳細限制、代理與 frontier 提交流程見 [crawler/README.md](crawler/README.md)。

## Docker Compose

```bash
cp .env.example .env
# 修改 POSTGRES_PASSWORD、ADMIN_TOKEN、網址設定；展示時才設定 DEMO_MODE=true
# PostgreSQL 密碼請用不需 URL escaping 的長隨機英數字

docker compose up --build
```

前端 http://localhost:3000 、API http://localhost:8000 。PostgreSQL 不對外暴露；網站和 API 預設只綁本機。用 TLS 反向代理部署，將 `NEXT_PUBLIC_API_URL` 設成外部可訪問的 HTTPS API 網址再重新建置前端，更新 CORS。只有網站部署在 Cloudflare 而 API 不可訪問，不能運作此完整版本。Playwright 與 Python parser 不放入 Cloudflare Workers。

首次 schema 由 SQLAlchemy 建立。這是第一版，不提供已有生產 schema 的自動 migration；後續 schema 調整需引入 migration、備份與恢復流程。資料庫與 frontier volume 均需定期備份。

## 驗證

```bash
python -m pytest tests -q
python -m compileall -q backend crawler scripts
cd frontend
npm run typecheck
npm run build
```

GitHub Actions 執行相同後端測試與前端建置。測試使用本地 fixture，不需真實校網或模型 key；不代表已驗證全台網站發現率。

## 範圍與尚未完成事項

這是可運行的工程 MVP，**不是已完成全台資料蒐集的服務**。尚未啟用搜尋引擎補充發現、JS-only browser fallback、OCR、DOC/XLS legacy 轉換或 LLM extraction。全台官方 registry、20 校人工標註評估、95% extraction／90% discovery 的 KPI 尚未驗證。跨校表格保留原範圍文字，不宣稱已做出版社教材對照。歷屆試題推薦、通知、多管理員帳號、分散式佇列屬後續版本。

[產品範圍](docs/PRODUCT.md) · [架構](docs/ARCHITECTURE.md)

## 校方聯絡與退出索引

校方可透過 robots.txt 阻擋 `ExamRadarBot`；專案管理者亦可停用 registry 的 `crawl_enabled`。聯絡與更正可在 [GitHub Issues](https://github.com/steventeng2022/Exam-radar/issues) 提出，勿附私人學生資料。正式發布時設定 `CRAWLER_INFO_URL` 為公開的 `/crawler` 說明網址。

## v1.1 流程優化

搜尋與比較採 SQL 分頁，控制台加入文件人工整理、學校匯入／暫停、工作取消／重試、爬蟲在線狀態、文件原文與審核修正。所有人工修正保留來源及操作紀錄，舊頁面不能覆蓋已被修改的資料。後端更新詳見 [backend/README.md](backend/README.md)。

正式 Cloudflare 網站以 [Exam-radar-website](https://github.com/steventeng2022/Exam-radar-website) 為主；這個 monorepo 的 frontend 同步提供本地／Docker 開發版本。
