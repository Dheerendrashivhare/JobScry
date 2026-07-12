# AJH — Build Progress

> Read together with CLAUDE.md (master spec v2) at the start of every session.

## Phase status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Architecture | DONE (2026-07-10) | Scaffold + ARCHITECTURE.md + bootable skeleton; smoke test passing; awaiting owner approval |
| 2 | Database | DONE (2026-07-11) | 15 SQLAlchemy models + Alembic initial migration; model tests pass; ER diagram; awaiting owner approval |
| 3 | Authentication | DONE (2026-07-11) | Email+JWT (access+refresh), first-user=Admin, RBAC; 24 tests pass; live-run verified |
| 4 | Backend APIs | DONE (2026-07-11) | Profiles/skills, resumes, credentials(Fernet), settings, providers, searches; 41 tests pass |
| 5 | Job Provider Framework | DONE (2026-07-11) | 8 adapters + registry + ingestion pipeline (dedup/expiry/salary); 60 tests pass |
| 6 | AI Matching | DONE (2026-07-11) | Deterministic weighted scoring + gate + work-auth + LLM explanations; 81 tests pass |
| 7 | Scheduler | DONE (2026-07-11) | Celery + Redis, beat daily 03:00 UTC, per-user Redis lock; catch-up mode |
| 8 | Notifications | DONE (2026-07-11) | Telegram + Email; top-20 fresh cap, no minimum, never repeat; 85 tests pass |
| 9 | Angular Frontend | DONE (2026-07-12) | Angular 19 (see deviation), Material+Tailwind, dark mode, lazy routes, JWT interceptor; `ng build` clean |
| 10 | Testing | DONE (2026-07-12) | Backend 85 (pytest) + frontend 19 (Vitest/jsdom) = **104**; found + fixed a real interceptor bug |
| 11 | Deployment | DONE (2026-07-12) | Dockerfiles, 6-service compose, Nginx, CI. **Images NOT built locally — Docker daemon unresponsive here** |
| 12 | Documentation | DONE (2026-07-12) | README, docs/DEPLOYMENT.md (+ existing ARCHITECTURE.md, DATABASE.md) |

## Key decisions log (2026-07-10)

- Dedup: simple URL/ID + role+company collapse; no fuzzy matching
- AI: rule-based scoring, LLM key (Anthropic/OpenAI) for explanations + résumé tailoring
- Auth: Email+JWT only · Notifications: Telegram + Email only
- Salary: raw as posted; LPA computed for INR only, no FX conversion
- Matches: gate ≥90, cap 20/run, no minimum, never inflate scores
- Providers: Adzuna, Jooble, JSearch, Remotive, Greenhouse/Lever, SerpAPI; Apify REST
  (fantastic-jobs LinkedIn actor, muhammetakkurtt Naukri actor); Wellfound dropped
- Scheduler: Celery + Redis (not APScheduler)
- Expiry check: best effort (date_valid_through + HTTP-check where possible)
- Work-auth: offshore w/o explicit sponsorship = eligibility-gated
- Résumés: PDF/DOCX/LaTeX, multi-upload, defensible tailoring only

## Phase 1 notes (2026-07-10)

- Repo at `ajh/`: backend scaffold (clean-architecture packages), frontend dirs (workspace
  init deferred to Phase 9), infra/, docs/ARCHITECTURE.md (4 Mermaid diagrams)
- Backend pins verified live: FastAPI 0.139.0, SQLAlchemy 2.0.51, Alembic 1.18.5,
  Celery 5.6.3, Pydantic 2.13.4, uvicorn 0.51.0, redis 8.0.1
- App-factory pattern, pydantic-settings config, /api/v1/health, pytest smoke test: PASSING
- CAVEAT: sandbox has only Python 3.10 (3.12 install blocked by network policy). Code targets
  3.12; sandbox tests run on 3.10. Final 3.12 verification = owner's Docker build (python:3.12-slim).
- Per-user encrypted provider credentials (Fernet) decided — keys in DB, not env

## Phase 2 notes (2026-07-11)

- 15 models under `backend/app/models/` (all §15 tables + `matches` for scored results):
  users, profiles, skills, profile_skills, resumes, jobs, job_skills, matches, seen_jobs,
  providers, credentials, settings, searches, applications, notifications.
- SQLAlchemy 2.0 typed models (`Mapped`/`mapped_column`); `database/base.py` (DeclarativeBase +
  constraint naming convention + `TimestampMixin` + `enum_column`), `database/session.py`
  (lazy async engine/sessionmaker + `get_db` dependency — no import-time DB connection).
- Enums stored as `VARCHAR + CHECK` (`native_enum=False`, `values_callable` → lowercase
  values) for portability + clean migrations. List-like profile config (target roles,
  companies, locations, weights…) in JSON columns; only skills normalized (per §15 list).
- Alembic wired: async `env.py` reads `Settings.database_url`; initial migration
  `1fd90d563f5e_initial_schema` creates all 15 tables. Verified with full upgrade→downgrade
  round-trip (on aiosqlite locally; production applies on Postgres via asyncpg).
- Tests: `tests/test_models.py` (10 pass) — schema builds, relationships, ORM cascade,
  defaults, enum-as-value, unique constraints — bound to sync in-memory SQLite (driver-free).
- Quality gates green: ruff, isort, black (aligned via `combine-as-imports`), pytest.
- ER diagram + table/decision notes in `docs/DATABASE.md`; migration usage in
  `backend/alembic/README.md`. Added `aiosqlite` dev dep; ignore local `*.db`.
- DEVIATION from Phase-1 plan: `database/session.py` engine is now lazy (was eager in the
  scaffold) so importing models never requires the DB driver.

## Phase 3 notes (2026-07-11)

- Email + JWT auth (§12). Endpoints: `POST /api/v1/auth/register|login|refresh`,
  `GET /api/v1/auth/me`, `GET /api/v1/auth/users` (admin-only).
- **Registration policy (owner decision):** open self-registration; the first account
  ever created becomes Admin, everyone after is User. No public admin-creation.
- `core/security.py`: passwords via passlib `bcrypt_sha256` (no 72-byte limit);
  JWT access + refresh with a `type` claim (access can't be used as refresh or vice-versa),
  signed with `Settings.secret_key`. `bcrypt` pinned to 4.0.1 (passlib 1.7.4 reads
  `bcrypt.__about__`, removed in bcrypt>=4.1). Added `email-validator` for `EmailStr`.
- `core/exceptions.py`: `AppError` hierarchy + single handler → `{detail, code}` JSON
  (401s carry `WWW-Authenticate: Bearer`). Services raise domain errors, never HTTPException.
- `api/deps.py`: `get_current_user` (HTTPBearer), `CurrentUser`, `require_admin`/`AdminUser`
  RBAC guards, `DBSession`. Repository (`repositories/user.py`) + service
  (`services/auth.py`) own data access and the transaction boundary respectively.
- Tests: `tests/test_auth.py` (14) over the ASGI app with an aiosqlite `get_db` override —
  registration policy, login, refresh, current-user, RBAC, validation. Suite now **24 pass**.
- **Live-run verified** (`/verify`): ran uvicorn on a SQLite-backed DB and drove the real
  socket — happy path + 10 probes all correct (first=admin/second=user, 409 dup, 422 bad
  email/short pw, 401 wrong-pw/unknown/no-token/wrong-token-type, 403 RBAC, case-insensitive
  login). Note: on SQLite `created_at` serialized tz-naive; on Postgres (`DateTime(timezone=True)`)
  it will carry the UTC offset.

## Phase 4 notes (2026-07-11)

- Clean-architecture slices (schema DTO → repository → service → route) for: profiles+skills,
  resumes, credentials, settings, providers, searches. 32 API routes, all JWT-protected.
- `core/crypto.py`: Fernet encrypt/decrypt/mask for stored secrets (added `cryptography` dep).
  Key from `Settings.credentials_encryption_key`; any passphrase is stretched to a valid Fernet
  key so the app runs without a key-gen step. Plaintext never leaves the service (masked hints only).
- **Profiles** (`/profiles`): CRUD scoped to the user; one default enforced; skills normalized via
  a canonical `skills` table (case-insensitive get-or-create); JSON config lists + scoring weights.
- **Searches** (`/profiles/{id}/searches`) + **Resumes** (`/profiles/{id}/resumes`): nested,
  ownership-checked. Resumes: multipart upload, PDF/DOCX/LaTeX only, 5 MB cap, stored on disk under
  `resume_storage_dir/<user_id>/`, `parse_status=pending` (extraction is a later phase), download route.
- **Credentials** (`/credentials`): PUT upsert (encrypted), GET list (masked), DELETE.
- **Settings** (`/settings`): GET/PATCH, lazily created; **Providers** (`/providers`): self-seeding
  8-provider catalog, admin-only enable/disable.
- Cross-cutting: `AppError` hierarchy (404/409/413/422/500 codes), `Page[T]` + `Pagination`
  (limit/offset, `Pagination` lives in `schemas.common` so services don't import the API layer).
- Notable fixes: 204 routes need `response_model=None` (FastAPI rejects a body model on 204);
  async read-after-write uses `populate_existing=True` so freshly-committed skills show up; insert
  `ProfileSkill` by FK (never touch the lazy collection) to avoid MissingGreenlet.
- Tests: `tests/test_api.py` (17) over the ASGI app (aiosqlite `get_db` override, shared
  `conftest.py`) — profiles/skills, credentials masking, settings, providers RBAC, searches,
  resume upload/format/primary/download, and per-user isolation. Full suite: **41 pass**.

## Phase 5 notes (2026-07-11)

- `providers/base.py`: `JobProvider` ABC (`search_jobs` → raw dicts, `normalize` → `NormalizedJob`,
  `health_check`) + `SearchQuery`/`NormalizedJob`/`ProviderHealth` DTOs. Adapters never touch the DB.
- **8 adapters** (`providers/adapters/`): Remotive, Greenhouse+Lever (free, board tokens via search
  params), Adzuna, Jooble, JSearch/RapidAPI, SerpAPI Google Jobs, Apify LinkedIn
  (`fantastic-jobs~advanced-linkedin-job-search-api`), Apify Naukri
  (`muhammetakkurtt~naukri-job-scraper`). Apify uses the REST `run-sync-get-dataset-items` endpoint
  with the user's token; the LinkedIn recipe (titleSearch/descriptionSearch/…) passes through verbatim.
- `providers/registry.py`: a provider is enabled for a user only when it's active in the catalog AND
  all its required credentials exist in that user's encrypted store. Remotive + Greenhouse/Lever need
  none, so they're always on.
- Domain (pure, unit-tested): `salary.py` — LPA computed **only for INR** (₹ LPA / lakh / crore /
  monthly / absolute / ranges; "competitive" and non-INR → null, no FX, §10); `dedup.py` — URL/ID
  normalization for stable dedup keys + expiry check (§6).
- `services/ingestion.py`: search → normalize → drop expired → collapse dupes → dedup vs the profile's
  `seen_jobs` → store Jobs + JobSkills + SeenJobs; provider failures isolated (retry-once → mark
  unhealthy → continue, §5); provider health persisted to the catalog; `last_run_at` stamped.
  Exposed as `POST /api/v1/profiles/{id}/ingest` (Phase 7's scheduler will call the same service).
- Outbound HTTP is an injectable `get_http_client` dependency → tests swap in an httpx `MockTransport`.
- Tests: `test_providers_domain.py` (17, salary/dedup/expiry) + `test_ingestion.py` (2, full pipeline
  over the ASGI app with mocked provider HTTP incl. re-run dedup). Full suite: **60 pass**.

## Phase 6 notes (2026-07-11)

- `matching/scoring.py` — pure, deterministic weighted engine (§7). Dimensions: tech-stack 40 /
  experience 20 / role 20 / domain 10 / source-quality 10 (per-profile weights). Required skills
  count double. Experience parsed from the posting ("3-5 years", "5+ yrs"); unstated → neutral 70,
  never a free pass. Source quality ranks company ATS (Greenhouse/Lever) above aggregators, with a
  direct-apply/named-recruiter bonus. Bands 95+/92+/90+; **gate = profile.min_score (default 90)**.
- **Integrity (§7) is structural, not a promise:** the score is computed by the engine and the gate
  applied to it *before* the LLM is ever constructed. The LLM cannot raise a score, un-gate a job, or
  add one — an LLM failure degrades to "no explanation", never to a changed result. Tests assert a
  near-miss (69) stays below the gate rather than being nudged to 90.
- `matching/eligibility.py` (§8): India / India-eligible-remote → **actionable**; offshore without
  stated sponsorship → **eligibility-gated** (surfaced honestly, not deleted). The recommendation text
  explicitly tells the owner to raise eligibility with the recruiter rather than declare authorisation
  he doesn't have. Explicit "must be authorized to work in…" beats an open-remote reading.
- `matching/llm.py`: one port, two adapters (Anthropic + OpenAI) over httpx with the user's key.
  **Anthropic wire format verified against current docs** — `claude-opus-4-8`, `x-api-key` +
  `anthropic-version: 2023-06-01`, and *no* `temperature`/`top_p` (those now 400 on Opus 4.8, so the
  reflexive `temperature=0` would have broken every call). Handles `stop_reason: "refusal"`.
- Selection-odds mode (§9): when `company_size_mode` is on, jobs above `max_headcount` are excluded —
  but an *unknown* headcount is never dropped on a guess.
- Empty-state (§4): matching a profile with no skills returns **422 `profile_incomplete`** — we ask
  rather than score an empty profile.
- `settings.llm_model` column added (+ migration `2cde58a24092`) so the user picks provider *and* model.
- Routes: `POST /profiles/{id}/match`, `GET /profiles/{id}/matches`. Result reports honest counts
  (evaluated / qualified / below_gate / excluded_by_size / eligibility_gated).
- Tests: `test_matching_domain.py` (17, pure) + `test_matching.py` (4, ingest→score→list end-to-end).
  Full suite: **81 pass**.

## Phases 7-8 notes (2026-07-11)

- **Pipeline (§14):** `services/pipeline.py` chains search → normalize → expiry → dedup →
  match → store → notify. The manual HTTP trigger and the Celery beat task call the *same*
  `PipelineService`, so they can never drift. `POST /api/v1/profiles/{id}/run?mode=daily|catchup`
  (catch-up widens the window to 7 days); `POST /api/v1/profiles/{id}/notify` sends only.
- **Scheduler:** `scheduler/celery_app.py` (Celery + Redis, **not** APScheduler), beat fires
  `ajh.dispatch_daily_pipelines` at 03:00 UTC, which fans out one `ajh.run_profile_pipeline`
  per profile that has an active search (unconfigured profiles never trigger provider calls, §4).
  Celery is sync, services are async → each task owns an `asyncio.run` loop, DB session and HTTP client.
- **Per-user lock (§14):** `scheduler/locks.py` — Redis `SET NX EX`, released by a compare-and-delete
  Lua script so an overrunning run can't delete a lock that now belongs to someone else. A task that
  finds the lock held returns `{skipped: true}` rather than failing or retry-storming.
- **Notifications (§13):** Telegram (Bot API) + Email (stdlib SMTP, run off the loop via
  `asyncio.to_thread` — no new dep). A channel is only built when it's *enabled* AND its secret exists.
- **The §7 rules live in `services/notification.py`, not the adapters:** cap = top 20 fresh matches,
  **no minimum** (3 matches → 3 sent, never padded); actionable-now roles lead, eligibility-gated ones
  follow and are labelled (§8); a match is marked notified **only after a channel actually accepted it**,
  so a failed send retries next run instead of silently swallowing the job.
- **Deliberate behaviour:** only jobs that *clear the gate* are persisted as matches, so below-gate jobs
  are re-scored on each run. That's intentional — if the owner later adds a skill or retunes weights, a
  previously-rejected job gets reconsidered instead of being buried forever.
- Tests: `test_pipeline.py` (4) drives the whole chain over the ASGI app with Remotive **and** the
  Telegram Bot API served by an httpx `MockTransport` — gate enforcement, honest counts, never-repeat,
  and "no notifier configured still scores". Full suite: **85 pass**. `alembic check` reports no drift.

## Phase 9 notes (2026-07-12)

- **DEVIATION from §2 ("pin latest stable"), owner-approved 2026-07-12:** pinned **Angular 19.2.27**,
  not the latest (22.0.6). Latest Angular requires Node ≥22.22.3; the owner's machine runs Node 20.11.1,
  and Angular 19 is the newest line whose engine range includes ^20.11.1 exactly. Owner chose "pin
  Angular 19, keep Node 20" over upgrading Node or building only in Docker. Revisit when Node is upgraded.
- Also pinned for Angular-19 peer compatibility: `ng-apexcharts@1.15.0` (2.x demands Angular ≥20),
  `ag-grid@33`, `@ngx-translate@16`, `tailwindcss@3`. No `--force`/`--legacy-peer-deps` anywhere —
  the dependency graph resolves cleanly.
- Standalone components + signals + lazy-loaded routes (§3). `core/` holds models, `ApiService`
  (one typed client for the whole backend), `AuthService`, `ThemeService`, the JWT interceptor and guards.
- **JWT interceptor** attaches the token and transparently refreshes on a 401 — concurrent 401s queue on
  the single in-flight refresh instead of each firing their own and racing each other into a logout.
- **Dark mode (required, §2)** is the default: one `dark` class on `<html>` drives both Material's system
  tokens and Tailwind's `dark:` variants, so a single toggle flips everything. Tailwind preflight is off
  so it doesn't fight Material's reset.
- **No CORS layer needed on the backend:** the API base is the relative `/api/v1`; `ng serve` proxies via
  `proxy.conf.json` and Nginx does the same in production.
- Screens wired to the real API: login/register (first account = Admin), dashboard (profile picker,
  daily/catch-up pipeline runner, ApexCharts breakdown, per-provider health), matches (AG Grid, with the
  eligibility-gated column called out), profiles, providers (admin-only toggles), settings (LLM provider/model,
  Telegram/email, encrypted API keys shown masked), admin (user list). ngx-translate wired via `public/i18n/en.json`.
- Gate check (§17): `ng build` **exit 0, no errors**, 579 kB initial. Bundle budget raised to 1.5 MB —
  AG Grid + ApexCharts + Material legitimately exceed the 500 kB default. Remaining Sass deprecation
  warnings come from Angular Material's own theme mixin, not our code.

## Phases 10-12 notes (2026-07-12)

### Phase 10 — Testing (104 tests total)

- Backend: **85** (pytest, in-memory SQLite — no DB service needed).
- Frontend: **19** (Vitest + jsdom): auth interceptor (7), route guards (5), theme service (3),
  login component (4).
- **DEVIATION (§17 "Frontend: Vitest") — resolved, not skipped:** Angular 19 has no first-party
  Vitest builder (that lands in Angular 20+). Used **AnalogJS** (`@analogjs/vite-plugin-angular` +
  `@analogjs/vitest-angular`), the supported route for Angular 17-19. Karma/Jasmine was removed so
  there is exactly one way to run tests. Bonus: jsdom means **no Chrome needed**, locally or in CI.
- More Angular-19-pin knock-on pins (same class of problem as `ng-apexcharts` in Phase 9):
  **Analog must be 1.22.5, not 2.x** (2.x targets Angular 20+ and fails to resolve Angular's
  fesm2022 testing bundle); **jsdom 25, not 29** (29 pulls a transitive dep that `require()`s an
  ESM module — broken on Node 20). Also needed `resolve.mainFields: ['module']` in `vite.config.mts`,
  and an explicit `@oxc-parser/binding-win32-x64-msvc` install (npm optional-dependency bug on Windows).
- **The tests found a real bug.** The JWT interceptor called `logout()` **twice** on a failed
  refresh: the `/auth/refresh` 401 passes back through the interceptor itself, hitting the
  "is an auth call" branch, *and* the refresh error handler. Two logouts = two router navigations.
  The same branch also meant a **failed login logged you out — navigating away and wiping the
  "Incorrect email or password" message the user needed to read**. Fixed: a 401 from `/auth/login`
  or `/auth/refresh` is now treated as *the answer*, not a signal to refresh, and propagates to the
  caller. Added a regression guard for the double-logout and a case for "401 with no refresh token".

### Phase 11 — Deployment

- Six services: `postgres`, `redis`, `api`, `worker`, `beat`, `web` (Nginx). The API, worker and
  beat all run from **one** backend image with different commands, so they can't drift apart.
- **Only the API migrates** (`RUN_MIGRATIONS=1`); worker/beat `depends_on: api → service_healthy`,
  so they start only after migrations are applied and can never race each other on the same revision.
- Missing secrets fail loudly via compose's `${VAR:?message}` rather than booting insecure defaults.
- Nginx serves the SPA (with `index.html` fallback so a refresh on `/matches` doesn't 404), proxies
  `/api` → `api:8000` (**this is why the backend needs no CORS layer**), caches hashed assets forever
  and `index.html` never, and uses a 300s read timeout because pipeline runs block on provider calls.
- CI (`.github/workflows/ci.yml`): backend lint+tests+`alembic check`, frontend Vitest+build, and a
  job that **builds both Docker images**.
- ⚠️ **HONEST STATUS: the images were never built on this machine.** `docker --version` and
  `docker compose config` succeed because neither touches the engine; every command that needs the
  daemon (`docker build`, `docker info`) **hangs and times out** — the Docker daemon is unresponsive
  here. So compose is schema/interpolation-validated only. The CI `images` job and the owner's own
  `docker compose up -d --build` are the first real build.

### Phase 12 — Documentation

- Rewrote `README.md` (quickstart, what a run does, scoring table, the work-auth rule, provider keys,
  salary policy, local dev, layout) and added `docs/DEPLOYMENT.md` (service diagram, design decisions,
  config, backups + the "a backup is useless without the same encryption key" warning, troubleshooting).
- `docs/ARCHITECTURE.md` and `docs/DATABASE.md` already existed from Phases 1-2.

## Next steps

**All 12 phases are complete.** Remaining work is owner-side verification and polish:

1. **Run the stack** — `cp .env.example .env`, fill the two secrets, `docker compose up -d --build`.
   This is the first real Docker build (see the Phase 11 honesty note above); if the backend image
   fails, the likely cause is a wheel missing for `linux/amd64` on Python 3.12 (local dev ran 3.13).
2. **First smoke run** — register (first account = Admin) → create a profile with skills → add a
   saved search → Dashboard → *Run pipeline*. Remotive needs no API key, so a run works with zero
   credentials configured.
3. **Not built (deliberately out of scope so far, all specced in CLAUDE.md):** résumé *parsing*
   (upload + parse-status exist; text extraction from PDF/DOCX/LaTeX does not), per-role résumé
   *tailoring* execution (LLM client + prompts exist, no endpoint wires it), the applications
   tracker UI, and the analytics screen. The backend models for all of these already exist.
4. **Revisit the Angular 19 pin** when Node is upgraded to ≥22 (see Phase 9 deviation).
