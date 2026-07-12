# AJH — AI Job Hunter

Finds currently-open roles that genuinely fit you, scores them honestly, and tells you about
the ones worth your time. **A smaller list of true fits beats a padded list of stretches** —
the scorer is deterministic and is never allowed to inflate a number to hit a target count.

Personal-scale: you and a few friends, not a SaaS.

---

## Quickstart (Docker)

You need Docker Desktop. Nothing else.

```bash
cp .env.example .env
```

Fill in the two secrets in `.env`:

```bash
# Signs JWTs
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encrypts your stored API keys at rest
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then:

```bash
docker compose up -d --build
```

| URL | What |
|---|---|
| http://localhost:8080 | The app |
| http://localhost:8000/docs | API docs (OpenAPI) |

**The first account you register becomes the Admin.** Open the app, create it, then:

1. **Profiles** — add your skills, target roles, locations, experience band. Skills drive 40%
   of the score, so a profile with no skills cannot match anything.
2. **Settings** — add keys for the providers you want (all optional; Remotive and
   Greenhouse/Lever need none). Add an LLM key only if you want match explanations and résumé
   tailoring — scoring works fine without one.
3. **Dashboard** — pick a profile and hit **Run pipeline**.

> ⚠️ Changing `CREDENTIALS_ENCRYPTION_KEY` later makes every already-stored API key unreadable.
> You would have to re-enter them.

---

## What a run actually does

```
search providers → normalize → drop expired → deduplicate → score → store → notify
```

- **Deduplicate** against a permanent per-profile store keyed on the listing URL/ID, so a run
  only ever surfaces *new* listings.
- **Score** deterministically (below). No LLM touches the number.
- **Notify** the top 20 fresh matches via Telegram/email — **and there is no minimum.** If a
  run yields three, you get three. Nothing is padded, and nothing is ever sent twice.

Runs happen nightly (03:00 UTC, Celery beat) and on demand. A **catch-up** run widens the
window from 24 hours to 7 days.

## How scoring works

| Dimension | Weight |
|---|---|
| Tech-stack match | 40 |
| Experience match | 20 |
| Role match | 20 |
| Domain / company fit | 10 |
| Source quality + direct-apply trust | 10 |

Weights are per-profile and editable. **Gate at ≥ 90**: 95–100 High · 92–94 Medium-High ·
90–91 Stretch. Anything below 90 is not stored as a match.

A realistic window yields **4–10 genuine ≥90 matches**; a >95 shows up once or twice a week.
If a run finds 6, it reports 6.

Only jobs that clear the gate are persisted, so below-gate jobs are re-scored on every run.
That is deliberate: add a skill or retune your weights, and previously-rejected jobs get
reconsidered instead of being buried forever.

## Work authorization (read this one)

You are India-based. Every match is flagged:

- **Actionable** — India roles (any mode) and India-eligible remote roles.
- **Eligibility-gated** — offshore roles with no stated sponsorship. Still shown, clearly
  labelled, and sorted after the actionable ones.

The app will **never** advise you to answer "yes, I am legally eligible" when you are not.
Raise it with the recruiter; don't let it silently sink an application, and don't spend energy
on walls that won't move.

---

## Providers

| Provider | Needs a key |
|---|---|
| Remotive | — |
| Greenhouse / Lever boards | — |
| Adzuna | `adzuna_app_id`, `adzuna_app_key` |
| Jooble | `jooble_key` |
| JSearch | `rapidapi_key` |
| Google Jobs | `serpapi_key` |
| LinkedIn (Apify) | `apify_token` |
| Naukri (Apify) | `apify_token` |

A provider only runs for you once its keys are stored. Failures are isolated: a provider that
times out is retried once, marked unhealthy, and the run continues without it.

**Search tips that actually matter:**

- **LinkedIn** — broad titles + tech-in-description massively out-performs narrow queries.
  Pair `titleSearch: [Backend Engineer, Backend Developer, Python Developer, …]` with
  `descriptionSearch: [Python, FastAPI]`.
- **Naukri** — search `"FastAPI Backend Developer"`, never bare `"Python"`; the latter floods
  you with AI/ML-trainer and data-science roles.
- Company-owned portals (IBM, Deloitte USI, PwC, Siemens) aren't fully indexed by LinkedIn
  scrapers — search those directly when you're targeting a specific brand.

## Salary

Shown **raw as posted**. LPA is computed **only for INR** postings (₹ LPA, lakh, crore, monthly
amounts, ranges). No FX conversion — a US role stays `$120,000` rather than being converted into
a misleading LPA figure.

---

## Local development

**Backend** (Python 3.12+):

```bash
cd backend
pip install -e ".[dev]"
pytest -q                    # 85 tests; no database needed (in-memory SQLite)
uvicorn app.main:app --reload
```

**Frontend** (Node 20):

```bash
cd frontend
npm ci
npm start                    # proxies /api → localhost:8000, so no CORS layer is needed
```

**Lint gates** (identical to CI):

```bash
cd backend
ruff check app tests && isort --check-only app tests && black --check --line-length 100 app tests
```

**Database changes:**

```bash
cd backend
alembic revision --autogenerate -m "what changed"
alembic upgrade head
alembic check                # fails if a model drifted from the migrations
```

---

## Architecture

- **Backend** — FastAPI, SQLAlchemy 2 (async), PostgreSQL, Alembic, Celery + Redis, Pydantic v2.
  Clean architecture: routers → services → repositories. No business logic in routers.
- **Frontend** — Angular 19, standalone components + signals, Angular Material + Tailwind,
  lazy-loaded routes, dark mode by default.
- **Secrets** — your provider/LLM keys are Fernet-encrypted in the database. They are never
  returned to the browser; the UI only ever shows a mask (`****1234`).

Diagrams and the ER model: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
[`docs/DATABASE.md`](docs/DATABASE.md). Deployment detail: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
Build history and decisions (including deviations): [`PROGRESS.md`](PROGRESS.md).

## Project layout

```
backend/
  app/
    api/           routers (presentation)
    services/      use-cases (application) — ingestion, matching, notification, pipeline
    matching/      scoring + eligibility + LLM client
    providers/     job-provider adapters + registry
    repositories/  SQLAlchemy data access
    scheduler/     Celery app, tasks, per-user Redis lock
  alembic/         migrations
  tests/           85 tests
frontend/          Angular 19 SPA
infra/nginx/       reverse proxy (serves the SPA, proxies /api)
docs/              architecture, database, deployment
```
