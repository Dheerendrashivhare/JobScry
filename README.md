# AJH — AI Job Hunter Platform

Personal AI recruiter: multi-provider job search, honest AI scoring (gate ≥90),
résumé tailoring, application tracking. Angular + FastAPI + PostgreSQL + Celery/Redis.

Spec: see project `CLAUDE.md` (master spec v2). Progress: `PROGRESS.md`.
Architecture: `docs/ARCHITECTURE.md`.

## Quick start (backend, local)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # edit values
pytest                  # smoke tests
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

Docker/compose arrive in Phase 11. Frontend workspace initialized in Phase 9.
