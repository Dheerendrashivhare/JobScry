# AJH — Build Progress

> Read together with CLAUDE.md (master spec v2) at the start of every session.

## Phase status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Architecture | DONE (2026-07-10) | Scaffold + ARCHITECTURE.md + bootable skeleton; smoke test passing; awaiting owner approval |
| 2 | Database | not started | |
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

## Next steps

1. Owner approval of Phase 1
2. Phase 2 (Database): SQLAlchemy models for all tables (CLAUDE.md §15), Alembic setup,
   ER diagram, initial migration
