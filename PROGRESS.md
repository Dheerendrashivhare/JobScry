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
| 7 | Scheduler | not started | Celery + Redis |
| 8 | Notifications | not started | Telegram + Email |
| 9 | Angular Frontend | not started | Build-check at phase gate only |
| 10 | Testing | not started | |
| 11 | Deployment | not started | Owner runs Docker manually |
| 12 | Documentation | not started | |

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

## Next steps

1. Phase 7 (Scheduler): Celery + Redis, per-user lock, daily (24h) + catch-up (3-7d) windows, chaining
   the existing ingestion → matching services. Then Phase 8 (Notifications: Telegram + Email, top-20
   fresh cap, never repeat). Owner authorized autonomous progress.
