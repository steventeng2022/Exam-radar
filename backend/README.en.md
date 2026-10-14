# API / worker

[繁體中文 / original guide](README.md) | **English**

Run from the repository root. The project's documented development environment uses Python 3.12+:

```bash
pip install -r requirements.txt
python -m backend.registry initialize --demo
DEMO_MODE=true uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

After the API has initialized the database, start the worker in a separate terminal using the same database configuration:

```bash
python -m backend.worker loop
```

Run backend tests from the repository root:

```bash
python -m pytest tests/backend
```

The environment-variable syntax above is for Bash. See the [main setup guide](../README.en.md#local-setup) for PowerShell syntax.

## Configuration and registry

`DATABASE_URL` defaults to `sqlite:///./exam-radar.db`; production uses `postgresql+psycopg://...`.

`DEMO_MODE=true` explicitly creates labeled synthetic examples when the database is empty. Demo schools cannot be crawled. Import real school data separately:

```bash
python -m backend.registry initialize --import-json schools.json
```

The JSON file contains an array of objects with `id`, `name`, `short_name`, `city`, `district`, `website`, `domains`, `type`, and `crawl_enabled`. Imports validate registered `.edu.tw` domains. This registry is not claimed to be a nationwide official school inventory.

`ADMIN_TOKEN` enables admin routes. Set it when starting the API and pass `Authorization: Bearer TOKEN` in admin requests. Without a configured token, admin routes are disabled with HTTP 503.

`CORS_ORIGINS` is a comma-separated allowlist, defaulting to `http://localhost:3000`. `CRAWLER_STATE_DIR` defaults to `./data/frontier`; persist this directory and the database. Public API documentation is available at `/docs`.

## Public API

Search endpoint:

```text
/api/exams?q=&city=&school_id=&grade=&academic_year=&semester=&number=&subject=&limit=&offset=
```

Responses contain `{items,total,demo}`. Version details include source URL, title, fetch time, content hash, per-subject evidence, and page number. Unapproved versions remain hidden from the public.

Comparison presents matching exam scopes; it does not infer curriculum coverage.

## Admin API and worker

Core endpoints:

- `POST /api/admin/crawl/{school_id}`
- `GET /api/admin/crawls`
- `GET /api/admin/review`
- `POST /api/admin/review/{version_id}/approve`
- `POST /api/admin/review/{version_id}/reject`

The worker claims persistent jobs, parses documents, validates source identity and exam fields, and acknowledges crawler content hashes only after a successful database commit. Rule-based extractions enter human review.

Run only one active worker per database. Although PostgreSQL job locking supports concurrent claims, recovery of abandoned jobs requires a single worker supervisor. The current global lease enforces one active worker.

The base scheduling policy checks enabled registered schools every 24 hours, or every 6 hours when documents have been fetched within the past 7 days. Failed schools receive a 48-hour backoff; v1.1 adds exponential backoff for repeated complete failures, capped at one week.

Production schema migrations remain a future step. No automatic nationwide registry is enabled.

## v1.1 workflows

- Public search and comparison select the latest published versions, apply filters, and paginate in SQL. `GET /api/filters` returns filter options and public record counts. Lists include only the current version; detail views load publication history.
- The admin dashboard can import school JSON, enable or pause crawling, cancel jobs, and requeue failed jobs. Batch imports validate the entire batch before applying changes, and crawling is disabled by default.
- `POST /api/admin/review/{id}/edit` updates dates and subjects in a pending version. It requires a reason and `expected_revision`. Dates must fall between August of the academic year and July of the next year; duplicate subjects are not allowed.
- Approval and rejection can also include `expected_revision`. HTTP 409 means the data has changed and must be reloaded. Published versions cannot be overwritten through the review page.
- Edits, reviews, school settings, job queueing, and cancellations are recorded in `audit_logs`. A shared `ADMIN_TOKEN` does not provide individual administrator identity tracking.
- Parsed documents preserve text and page numbers, available through `/api/admin/documents` and `/api/admin/sources/{id}/document`. Stored page text is capped at 200,000 characters; truncation is marked. Original announcement links remain available for existing sources without stored text.
- The crawler updates its heartbeat every 15 seconds and uses a 180-second database lease to prevent duplicate worker processes. Interrupted jobs are recovered only after acquiring the lease. The admin summary shows worker status. Cancellation and suspension take effect before the next page fetch; they do not immediately interrupt an HTTP download already in progress.
- Repeated complete failures trigger exponential scheduling backoff, capped at one week. Set `CRAWLER_MAX_PAGES` to control pages per run, with a default of 40 and a maximum of 100.

## Upgrading and deployment

The new `audit_logs`, `worker_state`, and `crawl_documents` tables are created at startup without changing existing table columns.

Back up the database before upgrading. Stop the old crawler before deploying the new version. Do not run an older worker without lease support alongside the current worker.

Provider URLs beginning with `postgres://` or `postgresql://` are automatically adapted to the installed psycopg driver. The Docker API supports the platform-provided `PORT` variable and defaults to 8000.

Docker services support automatic restarts. The crawler waits for the API health check before starting. After an abnormal shutdown, the previous lease may take up to 180 seconds to expire before another worker can take over. Running jobs and crawl frontier state can then be recovered.

In addition to SQLite fixtures, GitHub Actions runs the admin and public API workflows against PostgreSQL 17.

## Manual document extraction

Use `POST /api/admin/sources/:sourceId/extract` with the academic year, semester, exam number, grade, date, subject scopes, and `reason`.

The existing source fixes the school identity. Results always enter review and are not published directly. Submitting the same source and exam identity again returns HTTP 409. The dashboard's source document text view provides the corresponding form.
