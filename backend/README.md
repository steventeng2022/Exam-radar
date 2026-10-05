# API / worker

Run from the repository root with Python 3.11+:

```bash
pip install -r requirements.txt
python -m backend.registry initialize --demo
DEMO_MODE=true uvicorn backend.main:app --host 0.0.0.0 --port 8000
python -m backend.worker loop
pytest tests/backend
```

`DATABASE_URL` defaults to `sqlite:///./exam-radar.db`; production uses `postgresql+psycopg://...`. `DEMO_MODE=true` explicitly creates labeled synthetic examples if the database is empty. Demo schools cannot be crawled. Real school data must be imported separately:

```bash
python -m backend.registry initialize --import-json schools.json
```

JSON contains an array of objects with `id`, `name`, `short_name`, `city`, `district`, `website`, `domains`, `type` and `crawl_enabled`. Import validates registered `.edu.tw` domains. It does not claim a national official school inventory.

`ADMIN_TOKEN` enables admin routes; pass `Authorization: Bearer TOKEN`. Missing token disables admin (503). `CORS_ORIGINS` is a comma-separated allowlist (default localhost:3000). `CRAWLER_STATE_DIR` defaults to `./data/frontier`; mount this directory and the database persistently. Public API docs: `/docs`.

Search: `/api/exams?q=&city=&school_id=&grade=&academic_year=&semester=&number=&subject=&limit=&offset=`. Responses return `{items,total,demo}`. Detail versions include source URL, title, fetched time, content hash, per-subject evidence and page number. Unapproved versions remain invisible publicly. Compare currently presents matched scopes; it does not infer curriculum coverage.

Admin: `POST /api/admin/crawl/{school_id}`, `GET /api/admin/crawls`, `GET /api/admin/review`, `POST /api/admin/review/{version_id}/approve|reject`. The worker claims persistent jobs, parses documents, validates source identity and exam fields, and acknowledges crawler hashes only after successful database commit. Rule-based extracts enter human review. Run one worker with SQLite. PostgreSQL job locking supports concurrent claims, but startup recovery of abandoned jobs currently requires a single worker supervisor. The worker schedules registered enabled schools every 24 hours, or 6 hours when documents were fetched within 7 days, and backs off failed schools for 48 hours. Production schema migrations remain an explicit next step; no automatic full-national registry is enabled.

## v1.1 工作流程

- 公開搜尋與比較在 SQL 中選取最新已發布版本、篩選與分頁。`GET /api/filters` 提供篩選選項及公開資料數量；列表只帶當前版本，詳細頁才載入發布歷史。
- 管理頁可匯入學校 JSON、啟用／暫停爬取、取消工作與重新排入失敗工作。批次匯入先驗證整批，預設不啟用爬取。
- `POST /api/admin/review/{id}/edit` 修改待審核的日期與科目，需要修改原因及 `expected_revision`。日期必須在該學年度八月至次年七月內；科目不可重複。
- 審核批准／拒絕也可附 `expected_revision`。409 表示資料已被修改，必須重新載入；已發布版本不可在審核頁改寫。
- 修改、審核、學校設定、工作排入與取消均保存 `audit_logs`；共用 ADMIN_TOKEN 不代表已具備個別管理者身分追蹤。
- 解析文件保存原文與頁碼，管理 API `/api/admin/documents` 及 `/api/admin/sources/{id}/document` 可查閱。文字保存上限為 200,000 字元的頁面內容；截斷會標示。既有來源未保存原文時仍可開啟原公告。
- 爬蟲每 15 秒更新 heartbeat，使用 180 秒資料庫 lease 防止第二個程序重複啟動。只有取得 lease 後才能恢復中斷工作，管理摘要會顯示在線狀態。取消與暫停會在下次頁面抓取前停止，不會立刻中止正在下載的 HTTP 請求。
- 排程對連續完全失敗採指數退避，最長一週。每輪頁數可用 CRAWLER_MAX_PAGES 設定，上限 100，預設 40。

新增的 `audit_logs`、`worker_state`、`crawl_documents` 都是新資料表，啟動時建立，不改寫原有資料表欄位。升級前備份資料庫，先停止舊版 crawler 再部署新版；不要讓沒有 lease 的舊 worker 與新版同時運行。

PostgreSQL provider 的 `postgres://` 和 `postgresql://` 會自動改用已安裝的 psycopg driver。Docker API 支援平台提供的 PORT，未指定時使用 8000。

人工整理：`POST /api/admin/sources/:sourceId/extract`，輸入學年度、學期、次數、年級、日期、科目範圍與 reason。學校由既存 source 固定，結果一律進審核，不直接發布；同來源與段考身份重複提交回傳 409。控制台「文件原文」提供對應表單。

Docker 服務支援自動重新啟動，crawler 等 API 健康檢查成功再啟動。非正常停止後，舊 lease 最長 180 秒到期才允許接手；保留 running 工作及 frontier 的恢復能力。GitHub Actions 除 SQLite fixture 外，也使用 PostgreSQL 17 重跑管理與公開 API 流程。
