# AJH Architecture

## 1. System context

```mermaid
graph TB
    U[User<br/>browser] --> FE[Angular SPA<br/>Nginx]
    FE -->|REST /api/v1 + JWT| BE[FastAPI Backend]
    BE --> PG[(PostgreSQL)]
    BE --> RD[(Redis<br/>cache + broker)]
    CW[Celery Workers] --> PG
    CW --> RD
    CB[Celery Beat<br/>daily schedule] --> RD

    subgraph External Providers
        A1[Adzuna] ; A2[Jooble] ; A3[JSearch/RapidAPI] ; A4[Remotive]
        A5[Greenhouse/Lever] ; A6[SerpAPI Google Jobs]
        AP[Apify REST<br/>LinkedIn + Naukri actors<br/>user API key]
    end
    CW --> A1 & A2 & A3 & A4 & A5 & A6 & AP

    subgraph Notifications
        TG[Telegram Bot] ; EM[SMTP Email]
    end
    CW --> TG & EM

    LLM[Anthropic / OpenAI API<br/>user key, optional] --- CW
```

## 2. Clean-architecture layers (backend)

```mermaid
graph TB
    subgraph Presentation
        R[API routers<br/>app/api/v1] --> S
    end
    subgraph Application
        S[Services<br/>use-cases, orchestration] --> RP
        S --> DTO[Pydantic schemas / DTOs]
    end
    subgraph Domain
        D[Domain models & rules<br/>scoring, work-auth logic,<br/>dedup keys, LPA parsing]
    end
    subgraph Infrastructure
        RP[Repositories<br/>SQLAlchemy] --> DB[(PostgreSQL)]
        PRV[Provider adapters<br/>Apify, Adzuna, ...]
        NTF[Notifier adapters<br/>Telegram, Email]
        LLMC[LLM client]
        TSK[Celery tasks]
    end
    S --> D
    S --> PRV & NTF & LLMC
    TSK --> S
```

Dependency rule: Presentation → Application → Domain. Infrastructure implements
interfaces defined in Application/Domain. No business logic in routers or Angular
components. Repositories are the only layer touching SQLAlchemy sessions.

## 3. Provider plugin design

```mermaid
classDiagram
    class JobProvider {
        <<abstract>>
        +name: str
        +requires_credentials: list[str]
        +search_jobs(query: SearchQuery) list[RawJob]
        +normalize(raw: RawJob) NormalizedJob
        +health_check() ProviderHealth
    }
    JobProvider <|-- AdzunaProvider
    JobProvider <|-- JoobleProvider
    JobProvider <|-- JSearchProvider
    JobProvider <|-- RemotiveProvider
    JobProvider <|-- GreenhouseLeverProvider
    JobProvider <|-- SerpApiGoogleJobsProvider
    JobProvider <|-- ApifyLinkedInProvider
    JobProvider <|-- ApifyNaukriProvider
    class ProviderRegistry {
        +register(provider)
        +enabled_for(user) list[JobProvider]
    }
    ProviderRegistry o-- JobProvider
```

A provider is enabled for a user only when its required credentials exist in that
user's encrypted credential store. Apify providers activate when the user saves an
Apify API key. Failure policy (CLAUDE.md §5): timeout → retry once → mark unhealthy →
continue with remaining providers.

## 4. Scheduler pipeline (Celery)

```mermaid
sequenceDiagram
    participant B as Celery Beat
    participant W as Worker
    participant P as Providers
    participant DB as PostgreSQL
    participant N as Telegram/Email

    B->>W: run_pipeline(user_id) [per-user lock via Redis]
    W->>P: search_jobs() per enabled provider (24h / catch-up window)
    P-->>W: raw jobs
    W->>W: normalize → expiry-check (date_valid_through / HTTP) → dedup vs seen_jobs (URL/ID + role+company collapse)
    W->>W: score (rule-based weights, gate >=90)
    W->>DB: store jobs + matches + seen_jobs
    W->>W: LLM explanations / resume suggestion (if key present)
    W->>N: top <=20 fresh matches, never repeats, honest count
```

## 5. Repository layout

```text
ajh/
  backend/
    app/
      api/v1/        # routers only (Presentation)
      core/          # settings, security, logging
      services/      # use-cases (Application)
      schemas/       # Pydantic DTOs
      models/        # SQLAlchemy ORM models
      repositories/  # DB access (Infrastructure)
      providers/     # job-provider adapters
      matching/      # scoring engine + LLM client
      scheduler/     # celery app, tasks, locks
      notifications/ # telegram + email adapters
      auth/ users/ profiles/ jobs/ resumes/ applications/ analytics/ admin/
      database/      # session, base, alembic env
      tests/
    pyproject.toml   # pinned deps (see file)
  frontend/          # Angular workspace (initialized in Phase 9; version pinned then)
  infra/nginx/
  .github/workflows/
  docs/
```

## 6. Version pins (backend, verified 2026-07-10)

FastAPI 0.139.0 · SQLAlchemy 2.0.51 · Alembic 1.18.5 · Celery 5.6.3 · Pydantic 2.13.4 ·
pydantic-settings 2.14.2 · uvicorn 0.51.0 · redis-py 8.0.1 · asyncpg 0.30.0 · httpx 0.28.1 ·
PyJWT 2.10.1. Target Python 3.12+ (Docker image `python:3.12-slim`).
Angular version pinned at Phase 9 start per CLAUDE.md §2.

## 7. Key decisions in this phase

- **App-factory pattern** (`create_app()`) → clean test isolation, no import-time side effects.
- **Settings via pydantic-settings** with `lru_cache` — env-driven, no candidate-specific values.
- **Per-user provider credentials encrypted** (Fernet key in env) rather than global env keys —
  each user brings their own Apify/LLM/SerpAPI keys.
- **Celery Beat + Redis-lock per user** prevents overlapping runs (CLAUDE.md §14).
- **Scoring is Domain-layer pure code** — deterministic and unit-testable; LLM is an
  Infrastructure adapter used after gating, never for the score itself (integrity rule §7).
