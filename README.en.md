# Exam Radar 📡

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[繁體中文](README.md) | **English**

A search engine for school exam information across Taiwan: find publicly announced exam scopes, compare teaching progress, and trace original announcements and revisions.

The product and frontend/backend split take inspiration from [STA](https://sta-tw.org/) and the [STA monorepo](https://github.com/sta-tw/sta-tw.org). This is an independent implementation using Next.js, FastAPI, and a Python crawler. The project is not affiliated with STA or any school.

## Current features

- A responsive Traditional Chinese website with search, grade/city/subject filters, exam scope comparison, source references, and version history.
- A public FastAPI query API, with admin Bearer token protection for crawling and review endpoints.
- Prioritized school website discovery, robots.txt checks, rate limiting, retries, public domain/IP validation, and document size limits.
- HTML/PDF/DOCX/XLSX parsing, content hashes, conditional HTTP requests, and a persistent crawl frontier that can resume interrupted work.
- Conservative rule-based extraction and school identity checks; extracted results require human approval before publication.
- SQLite for local development, PostgreSQL for deployment, Docker Compose, and GitHub Actions checks.

**Demo data is not official school information.** Demo mode includes fictional exam scopes and dates for five schools and three grades, solely for testing interactions. Do not use it to prepare for actual exams. Crawling is disabled for demo schools. Production mode starts with an empty dataset and does not silently display fictional information.

## Local setup

Requirements: Python 3.12+ and Node.js 22+. From the repository root, run the following in Bash:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DEMO_MODE=true ADMIN_TOKEN=local-development-token uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In Windows PowerShell, use:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DEMO_MODE = "true"
$env:ADMIN_TOKEN = "local-development-token"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs). The comparison interface is at `/compare`, the admin dashboard at `/dashboard`, and the collection policy at `/crawler`.

The dashboard uses the `ADMIN_TOKEN` configured when starting the backend and keeps it only in page memory. Use a long random token in production instead of the example value.

Set the frontend API address in `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

This is a public backend address; never put a token in it. Set the correct value when building Next.js for production. `CORS_ORIGINS` is a comma-separated list of allowed frontend origins, defaulting to `http://localhost:3000`.

## Crawling and data review

To crawl a single authorized official school website and output JSON, run:

```bash
python -m crawler https://your-school.edu.tw --name 'Full official school name' --id school-id --max-pages 40 --state data/frontier.sqlite3
```

**This command does not publish data directly.** Create `data/` first. The website must be public, permit crawling through robots.txt, and provide a verifiable school identity. For a real school, pass its exact official name, including Chinese where applicable. Administrators must explicitly add domains hosting external attachments to the school's domain list; external links are not automatically trusted.

The AI provider is disabled by default. No OpenAI API key is required, and school documents are not sent to external models.

The persistent worker runs jobs queued through the admin API:

```bash
python -m backend.worker
```

Start the API first so the database tables are initialized. The worker and API must use the same `DATABASE_URL`. Run only one active worker per database. The current version uses a global lease to prevent a second worker from running concurrently.

See the [backend guide](backend/README.en.md) for registry imports and scheduling commands.

Rule-based extraction creates a version pending review only when it can confirm the school name, academic year, semester, exam number, a single grade, and subject scopes. Unknown dates remain empty. Mixed-grade tables and scanned PDFs may be saved as documents without extracted exam data; the crawler does not guess school identity or exam scopes.

See the [crawler guide](crawler/README.md) for limitations, proxy handling, and crawl frontier commit behavior.

## Docker Compose

```bash
cp .env.example .env
# Update POSTGRES_PASSWORD, ADMIN_TOKEN, and URL settings.
# Set DEMO_MODE=true only for demonstrations.
# Use a long random alphanumeric PostgreSQL password that needs no URL escaping.
docker compose up --build
```

In PowerShell, use `Copy-Item .env.example .env` for the first step.

The frontend is at [http://localhost:3000](http://localhost:3000) and the API at [http://localhost:8000](http://localhost:8000). PostgreSQL is not exposed externally; the website and API bind to localhost by default.

For deployment, use a TLS reverse proxy, set `NEXT_PUBLIC_API_URL` to the externally accessible HTTPS API address, rebuild the frontend, and update CORS. Hosting only the website on Cloudflare with an inaccessible API will not run this complete application. Playwright and the Python parsers do not run in Cloudflare Workers.

SQLAlchemy creates the initial schema. This first version does not automatically migrate existing production schemas. Future schema changes require migrations, backups, and a recovery process. Back up both database and crawl frontier volumes regularly.

## Validation

From the repository root:

```bash
python -m pytest tests -q
python -m compileall -q backend crawler
cd frontend
npm run typecheck
npm run build
```

GitHub Actions runs the backend tests and frontend build. Tests use local fixtures and require neither real school websites nor model API keys. These tests do not establish nationwide website discovery performance.

## Scope and unfinished work

This is a working engineering MVP, **not a service that has completed nationwide data collection**.

Supplemental search-engine discovery, a browser fallback for JavaScript-only sites, OCR, legacy DOC/XLS conversion, and LLM extraction are not enabled. A nationwide official school registry, evaluation against manually labeled announcements from 20 schools, and the 95% extraction / 90% discovery targets have not been validated.

Cross-school comparisons preserve the original scope text; they do not claim to map textbooks across publishers. Past-paper recommendations, notifications, multiple administrator accounts, and distributed queues are planned for later versions.

[Product scope](docs/PRODUCT.en.md) · [Architecture](docs/ARCHITECTURE.en.md)

## School contact and opting out

Schools can block `ExamRadarBot` in robots.txt. Project administrators can also disable `crawl_enabled` in the registry.

Submit contact requests or corrections through [GitHub Issues](https://github.com/steventeng2022/Exam-radar/issues), without private student information. For a public deployment, set `CRAWLER_INFO_URL` to the deployment's public `/crawler` information page.

## v1.1 workflow improvements

Search and comparison use SQL pagination. The dashboard supports manual document extraction, school imports and crawl suspension, job cancellation and retries, worker status, source document text, and review corrections.

All manual corrections preserve source references and audit records. Stale pages cannot overwrite data that has already changed. See the [backend guide](backend/README.en.md) for details.

The production Cloudflare website is maintained in [Exam-radar-website](https://github.com/steventeng2022/Exam-radar-website). This monorepo also provides the frontend for local and Docker development.

## Contributing

Bug reports, feature suggestions, and pull requests are welcome. See [CONTRIBUTING.en.md](CONTRIBUTING.en.md) for development steps, validation, and data submission guidelines.

## License

The project's original code and accompanying documentation are licensed under the [MIT License](LICENSE). Copyright © 2026 steventeng2022. Retain the copyright and license notices when using, modifying, or redistributing them.

Third-party dependencies retain their own licenses. In particular, [PyMuPDF](https://pymupdf.io/licensing), listed in requirements.txt, is available under AGPL-3.0 or a commercial license. This project's MIT license does not replace PyMuPDF's terms. When using, deploying, or distributing the complete application with this dependency, comply with the applicable AGPL obligations or obtain an appropriate commercial license.

Crawled or linked school announcements, exam papers, attachments, and other third-party content do not become MIT-licensed because this project is open source. Their rights remain with the respective rights holders.
