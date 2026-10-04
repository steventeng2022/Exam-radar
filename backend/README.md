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
