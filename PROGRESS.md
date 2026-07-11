# AJH — Build Progress

> Read together with CLAUDE.md (master spec v2) at the start of every session.

## Phase status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Architecture | DONE (2026-07-10) | Scaffold + ARCHITECTURE.md + bootable skeleton; smoke test passing; awaiting owner approval |
| 2 | Database | DONE (2026-07-11) | 15 SQLAlchemy models + Alembic initial migration; model tests pass; ER diagram; awaiting owner approval |
| 3 | Authentication | not started | Email+JWT only |
| 4 | Backend APIs | not started | |
| 5 | Job Provider Framework | not started | Free APIs + Apify (LinkedIn, Naukri) |
| 6 | AI Matching | not started | Rule-based + optional LLM |
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

## Next steps

1. Owner approval of Phase 1 + Phase 2
2. Phase 3 (Authentication): Email+JWT (access + refresh), password hashing (passlib/bcrypt),
   `User`/RBAC dependencies, register/login/refresh endpoints, `Credential` encryption helper
   (Fernet) for the per-user key store, auth tests. (Skip email-verify/reset per §12.)
