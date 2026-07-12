# AJH — Complete Handbook

Everything in one place: what the system is, how every piece fits, what you must configure
before it will run, how to connect an AI provider, how to deploy it, and how to change it.

> **Companion docs:** [`README.md`](../README.md) (quickstart) ·
> [`ARCHITECTURE.md`](ARCHITECTURE.md) (original design) · [`DATABASE.md`](DATABASE.md) (ER detail) ·
> [`DEPLOYMENT.md`](DEPLOYMENT.md) (ops detail) · [`PROGRESS.md`](../PROGRESS.md) (build history,
> decisions, deviations).

---

## Table of contents

1. [The mental model](#1-the-mental-model)
2. [Before you start — prerequisites](#2-before-you-start--prerequisites)
3. [Configuration](#3-configuration)
4. [Architecture & diagrams](#4-architecture--diagrams)
5. [Libraries — what, where, why](#5-libraries--what-where-why)
6. [Component walkthrough](#6-component-walkthrough)
7. [Connecting AI](#7-connecting-ai)
8. [Job providers & their keys](#8-job-providers--their-keys)
9. [Using the app day to day](#9-using-the-app-day-to-day)
10. [Deployment](#10-deployment)
11. [Making changes](#11-making-changes)
12. [Testing](#12-testing)
13. [Troubleshooting](#13-troubleshooting)
14. [Known gaps & honest status](#14-known-gaps--honest-status)

---

## 1. The mental model

AJH is a **job-hunting pipeline**, not a job board. One idea drives every design decision:

> **A smaller list of true fits beats a padded list of stretches.**

So the scorer is **deterministic** — plain arithmetic, no AI — and it is **never allowed to
inflate a number to reach a target count**. If a run finds three good roles, you get three.
If it finds zero, you get zero and it says so.

The AI (Anthropic or OpenAI) is **optional** and deliberately kept away from the score. It only
*explains* a score that already exists and tailors a résumé. **No AI key → scoring still works.**

There are three actors:

| Actor | Does what |
|---|---|
| **You (the browser)** | Configure profiles/keys, trigger runs, read matches |
| **The API** | Serves the SPA's requests; can run the pipeline synchronously |
| **The scheduler** | Runs the same pipeline nightly, unattended, and notifies you |

---

## 2. Before you start — prerequisites

### The only hard requirement

| Need | Version | Why |
|---|---|---|
| **Docker Desktop** | any recent | Runs the whole stack (Postgres, Redis, API, worker, beat, Nginx) |

That's it for *running* it.

### Only if you want to develop

| Need | Version | Why |
|---|---|---|
| **Python** | **3.12+** | Backend. `3.12` is the container's runtime |
| **Node** | **20.x** | Frontend. **Not 22+** — see the pin below |
| **Git** | any | Obviously |

> ### ⚠️ The Node/Angular pin — read this before upgrading anything
>
> Angular is pinned to **19**, not the latest (22). Latest Angular requires **Node ≥ 22.22.3**;
> this project targets **Node 20.11.1**, and Angular 19 is the newest line whose engine range
> includes it.
>
> That single pin cascades into three more:
>
> | Package | Pinned to | Because the newer one demands |
> |---|---|---|
> | `ng-apexcharts` | `1.15.0` | `2.x` → Angular ≥ 20 |
> | `@analogjs/*` | `1.22.5` | `2.x` → Angular ≥ 20 |
> | `jsdom` | `25` | `29` uses `require()` on an ESM module → breaks on Node 20 |
>
> **If you upgrade Node to 22**, all four can float back to current. Until then, `npm update`
> will fight you. This is logged as a deliberate deviation in `PROGRESS.md`.

### What you do *not* need

- No Postgres install (Docker provides it)
- No Redis install (Docker provides it)
- **No API keys at all** to start. Remotive and Greenhouse/Lever work with zero credentials.
- No AI key. Scoring runs without one.

---

## 3. Configuration

### 3.1 The two secrets you must set

Copy `.env.example` → `.env` and fill these two. **Compose refuses to boot without them**
(`${VAR:?message}`) — deliberately, so you can't accidentally run on an insecure default.

```bash
# SECRET_KEY — signs JWTs
python -c "import secrets; print(secrets.token_urlsafe(48))"

# CREDENTIALS_ENCRYPTION_KEY — encrypts your stored API keys at rest (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

| Variable | If you change it later |
|---|---|
| `SECRET_KEY` | Every existing login is invalidated. Users just sign in again. Harmless. |
| `CREDENTIALS_ENCRYPTION_KEY` | **Every stored API key becomes permanently unreadable.** You must re-enter them all. Treat it like a password you can never rotate casually. |

### 3.2 Every setting the backend reads

From `backend/app/core/config.py`. All are env vars (uppercase), all have defaults except the
two secrets.

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `production` / `test` |
| `DEBUG` | `false` | Echoes SQL when true |
| `SECRET_KEY` | `CHANGE_ME` | **Must set.** JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Short-lived access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Long-lived refresh token |
| `JWT_ALGORITHM` | `HS256` | |
| `DATABASE_URL` | `postgresql+asyncpg://ajh:ajh@localhost:5432/ajh` | **Must be an async driver** (`+asyncpg`, or `+aiosqlite` for tests) |
| `REDIS_URL` | `redis://localhost:6379/0` | Per-user pipeline lock |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Task queue |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Task results |
| `CREDENTIALS_ENCRYPTION_KEY` | `CHANGE_ME` | **Must set.** Fernet key for stored secrets |
| `RESUME_STORAGE_DIR` | `./var/resumes` | Where uploaded résumés land (`/data/resumes` in Docker) |
| `RESUME_MAX_BYTES` | `5242880` (5 MB) | Upload cap |

Plus compose-only: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `RUN_MIGRATIONS`
(set to `1` on the API container only — see §10).

### 3.3 What is *not* in the env file

**Your provider and LLM API keys are not environment variables.** They're entered in the
**Settings** screen, encrypted with Fernet, and stored per-user in the database. Reasons:

- Multi-user: your friend's Apify key isn't yours.
- They never reach the browser again — the UI only ever shows `****1234`.

---

## 4. Architecture & diagrams

### 4.1 System context (who talks to what)

```mermaid
graph TB
    U["👤 You<br/>(browser)"]

    subgraph AJH["AJH (your machine / your server)"]
        WEB["Nginx<br/>serves SPA + proxies /api"]
        API["FastAPI"]
        WRK["Celery worker"]
        BEAT["Celery beat<br/>(nightly 03:00 UTC)"]
        PG[("PostgreSQL")]
        RD[("Redis")]
    end

    subgraph EXT["External services (optional, your keys)"]
        JOBS["Job providers<br/>Remotive · Greenhouse/Lever · Adzuna<br/>Jooble · JSearch · SerpAPI · Apify"]
        LLM["LLM<br/>Anthropic or OpenAI"]
        NOTIF["Telegram · SMTP"]
    end

    U -->|HTTPS| WEB
    WEB -->|/api| API
    API --> PG
    API --> RD
    BEAT -->|enqueue| RD
    WRK -->|dequeue| RD
    WRK --> PG
    API -.->|manual run| JOBS
    WRK --> JOBS
    WRK --> LLM
    WRK --> NOTIF
```

### 4.2 Containers (what actually runs)

Six containers. **The API, worker, and beat are the same image** with different commands — so
they physically cannot drift apart.

```mermaid
graph LR
    subgraph "docker compose"
        direction TB
        WEB["web<br/>nginx:1.27-alpine<br/>:8080 → :80"]
        API["api<br/>ajh-backend<br/>:8000<br/>RUN_MIGRATIONS=1"]
        WRK["worker<br/>ajh-backend<br/>celery worker"]
        BEAT["beat<br/>ajh-backend<br/>celery beat"]
        PG[("postgres<br/>16-alpine<br/>vol: pgdata")]
        RD[("redis<br/>7-alpine<br/>vol: redisdata")]
        VOL[("vol: resumes")]
    end

    WEB --> API
    API --> PG
    API --> RD
    API --- VOL
    WRK --> PG
    WRK --> RD
    WRK --- VOL
    BEAT --> RD

    API -.->|healthy?| WRK
    API -.->|healthy?| BEAT
    API -.->|healthy?| WEB
```

**Why only the API migrates:** all three containers share one image. If all three ran
`alembic upgrade head` on boot they'd race on the same revision. So `RUN_MIGRATIONS=1` is set on
the API only; worker and beat `depends_on: api → service_healthy`, which means they don't start
until migrations have already been applied.

### 4.3 Backend layering (Clean Architecture)

Dependencies point **inward only**. A router never contains business logic; a service never
writes SQL; the domain knows nothing about HTTP or the database.

```mermaid
graph TD
    subgraph P["Presentation — app/api/"]
        R["routers<br/>auth · profiles · matches<br/>pipeline · settings · providers"]
        D["deps.py<br/>get_current_user · require_admin<br/>get_db · get_http_client"]
    end

    subgraph A["Application — app/services/"]
        S["IngestionService · MatchingService<br/>NotificationService · PipelineService<br/>ProfileService · CredentialService"]
        DTO["app/schemas/<br/>Pydantic DTOs"]
    end

    subgraph DOM["Domain — pure, no I/O"]
        SC["matching/scoring.py<br/>the weighted score"]
        EL["matching/eligibility.py<br/>work-auth gate"]
        SAL["providers/salary.py<br/>INR → LPA"]
        DED["providers/dedup.py<br/>URL → dedup key"]
    end

    subgraph I["Infrastructure"]
        REPO["app/repositories/<br/>SQLAlchemy — the ONLY place<br/>that touches a session"]
        ADP["app/providers/adapters/<br/>8 job-board clients"]
        LLM["matching/llm.py"]
        NOT["app/notifications/<br/>telegram · email"]
        TASK["app/scheduler/<br/>celery + redis lock"]
    end

    R --> S
    R --> D
    S --> DTO
    S --> DOM
    S --> REPO
    S --> ADP
    S --> LLM
    S --> NOT
    TASK --> S
    REPO --> DB[("PostgreSQL")]
```

### 4.4 The pipeline (the heart of the system)

```mermaid
sequenceDiagram
    autonumber
    participant T as Trigger<br/>(you, or beat)
    participant L as Redis lock
    participant P as PipelineService
    participant PR as Providers
    participant DOM as Scoring + Eligibility
    participant DB as PostgreSQL
    participant N as Telegram / Email

    T->>L: acquire lock user:{id}
    Note over L: SET NX EX — another run<br/>for this user? skip, don't queue
    L-->>P: acquired

    rect rgb(30,40,55)
    Note over P,PR: 1. INGEST
    P->>PR: search_jobs(query) per enabled provider
    PR-->>P: raw listings
    Note over P: retry once → mark unhealthy → CONTINUE<br/>(one bad provider never sinks the run)
    P->>P: normalize()
    P->>P: drop expired (date_valid_through)
    P->>P: collapse duplicates (URL/ID)
    P->>DB: SELECT seen_jobs → drop anything already shown
    P->>DB: INSERT new Jobs + JobSkills + SeenJobs
    end

    rect rgb(30,50,40)
    Note over P,DOM: 2. MATCH
    P->>DB: jobs seen by this profile, not yet matched
    P->>DOM: score_job() — pure arithmetic, NO AI
    DOM-->>P: score + component breakdown
    P->>DOM: assess_eligibility()
    DOM-->>P: actionable | eligibility-gated
    Note over P: score < gate (90)? → NOT stored.<br/>Never inflated to hit a count.
    P->>DB: INSERT Match (only those ≥ gate)
    opt LLM key present
        P->>P: explain each match (never changes the score)
    end
    end

    rect rgb(55,40,30)
    Note over P,N: 3. NOTIFY
    P->>DB: fresh matches (notified = false), cap 20
    Note over P: actionable first, then best score.<br/>NO MINIMUM — 3 matches ⇒ 3 sent.
    P->>N: send digest
    N-->>P: accepted
    P->>DB: mark notified = true (ONLY after a channel accepted)
    end

    P->>L: release (compare-and-delete)
```

### 4.5 How the score is computed

```mermaid
flowchart TD
    J["Job + Profile"] --> T["tech_stack<br/>weight 40"]
    J --> E["experience<br/>weight 20"]
    J --> R["role<br/>weight 20"]
    J --> D["domain<br/>weight 10"]
    J --> S["source_quality<br/>weight 10"]

    T --> T1["% of your skills the posting asks for<br/>required skills count double"]
    E --> E1{"Does the posting<br/>state years?"}
    E1 -->|no| EX["DROP the dimension<br/>and renormalize"]
    E1 -->|yes| E2["bands overlap → 100<br/>else penalize by distance"]
    R --> R1["title vs your target roles"]
    D --> D1["preferred → 100<br/>ignored → 0<br/>else → 60"]
    S --> S1["ATS 100 · LinkedIn 85 · Remotive 80<br/>+10 direct apply · +5 named recruiter"]

    T1 & E2 & EX & R1 & D1 & S1 --> W["weighted average<br/>over assessable dimensions"]
    W --> G{"score ≥ gate (90)?"}
    G -->|no| REJ["not stored<br/>reported honestly as below_gate"]
    G -->|yes| B["band:<br/>95-100 High · 92-94 Med-High · 90-91 Stretch"]
    B --> M["stored as a Match"]
```

> **Why "drop and renormalize" instead of a neutral guess:** originally an unstated experience
> requirement scored a "neutral" 70. That capped an otherwise-perfect job at **89** — one point
> under the gate — so a posting that simply didn't mention years **could never qualify, however
> well it fit.** You cannot fail a requirement nobody stated. Now the dimension is dropped and the
> remaining weights renormalize. (Found by actually running the thing; regression-tested.)

### 4.6 Work-authorization gate

```mermaid
flowchart TD
    J["Job"] --> I{"Location mentions<br/>India?"}
    I -->|yes| ACT["✅ ACTIONABLE"]
    I -->|no| SP{"Posting explicitly offers<br/>sponsorship / relocation?"}
    SP -->|yes| ACT
    SP -->|no| RM{"Remote / worldwide?"}
    RM -->|no| GATE["⚠️ ELIGIBILITY-GATED"]
    RM -->|yes| BLK{"Says 'must be authorized<br/>to work in X' / 'no sponsorship'?"}
    BLK -->|yes| GATE
    BLK -->|no| ACT

    GATE --> NOTE["Still shown, clearly labelled,<br/>sorted AFTER actionable ones.<br/><br/>NEVER tells you to claim<br/>eligibility you don't have."]
```

### 4.7 Data model (ER)

```mermaid
erDiagram
    users ||--o{ profiles : owns
    users ||--o| settings : has
    users ||--o{ credentials : "encrypted keys"
    users ||--o{ notifications : receives

    profiles ||--o{ profile_skills : declares
    skills   ||--o{ profile_skills : "shared vocabulary"
    skills   ||--o{ job_skills : "shared vocabulary"
    profiles ||--o{ resumes : has
    profiles ||--o{ searches : "query recipes"
    profiles ||--o{ matches : scored
    profiles ||--o{ seen_jobs : "dedup memory"
    profiles ||--o{ applications : tracks

    jobs ||--o{ job_skills : tagged
    jobs ||--o{ matches : scored
    jobs ||--o{ seen_jobs : recorded
    jobs ||--o{ applications : "applied to"

    matches }o--o| resumes : "tailored version"

    users {
        int id PK
        string email UK
        string hashed_password
        enum role "admin|user"
    }
    profiles {
        int id PK
        json target_roles
        json locations
        json scoring_weights "per-profile!"
        int min_score "the gate, default 90"
        bool company_size_mode
    }
    jobs {
        int id PK
        string dedup_key UK "normalized URL"
        enum provider_slug
        string title
        string company
        numeric salary_lpa_min "INR only"
        datetime valid_through
        bool is_expired
    }
    matches {
        int id PK
        int score "0-100"
        enum band
        enum eligibility_status
        json component_scores "the breakdown"
        text explanation "LLM, optional"
        bool notified "never repeat"
    }
    seen_jobs {
        int id PK
        string dedup_key "every job ever shown"
        datetime notified_at
    }
    credentials {
        int id PK
        enum key
        text encrypted_value "Fernet ciphertext"
    }
```

### 4.8 The provider plugin contract

Adding a job board = implementing one interface. Nothing else changes.

```mermaid
classDiagram
    class JobProvider {
        <<abstract>>
        +slug: ProviderSlug
        +requires_credentials: list
        +search_jobs(query) list~dict~
        +normalize(raw) NormalizedJob
        +health_check() ProviderHealth
    }
    class ProviderRegistry {
        +enabled_for_user(session, user_id)
    }
    note for ProviderRegistry "Enabled ONLY if the provider is active AND every credential it requires is stored for that user."

    JobProvider <|-- RemotiveProvider : no key
    JobProvider <|-- GreenhouseLeverProvider : no key
    JobProvider <|-- AdzunaProvider
    JobProvider <|-- JoobleProvider
    JobProvider <|-- JSearchProvider
    JobProvider <|-- SerpApiGoogleJobsProvider
    JobProvider <|-- ApifyLinkedInProvider
    JobProvider <|-- ApifyNaukriProvider

    ProviderRegistry o-- JobProvider
```

### 4.9 Auth & the token refresh dance

```mermaid
sequenceDiagram
    participant B as Browser
    participant I as authInterceptor
    participant A as API

    B->>I: GET /profiles
    I->>A: + Authorization: Bearer <access>
    A-->>I: 401 (access expired)

    Note over I: Is this /auth/login or /auth/refresh?<br/>Then the 401 IS the answer — don't refresh.
    I->>A: POST /auth/refresh { refresh_token }
    A-->>I: new access + refresh

    Note over I: Concurrent 401s QUEUE on this single<br/>in-flight refresh — they don't each fire<br/>their own and race into a logout.
    I->>A: retry GET /profiles with new token
    A-->>B: 200
```

### 4.10 Match lifecycle

```mermaid
stateDiagram-v2
    [*] --> Discovered : provider returns it
    Discovered --> Duplicate : dedup_key already in seen_jobs
    Duplicate --> [*] : silently skipped
    Discovered --> Expired : valid_through passed
    Expired --> [*] : dropped
    Discovered --> Scored : normalized + stored

    Scored --> BelowGate : score below the gate
    BelowGate --> Scored : re-scored on the next run

    Scored --> Qualified : score at or above the gate
    Qualified --> Notified : sent via Telegram or email
    Notified --> [*] : never sent again

    note right of BelowGate
        Not persisted as a Match.
        Reported honestly as below_gate.
        Re-scored every run, so adding a skill
        or retuning weights reconsiders it
        instead of burying it forever.
    end note
```

---

## 5. Libraries — what, where, why

### 5.1 Backend

| Library | Version | Where it lives | Why this one |
|---|---|---|---|
| **FastAPI** | 0.139.0 | `app/api/` | Async, typed, generates the OpenAPI docs for free |
| **Uvicorn** | 0.51.0 | container CMD | ASGI server |
| **SQLAlchemy** | 2.0.51 (asyncio) | `app/models/`, `app/repositories/` | Async ORM. Repositories are the **only** layer allowed to hold a session |
| **Alembic** | 1.18.5 | `backend/alembic/` | Migrations. `alembic check` in CI catches a model edited without a revision |
| **asyncpg** | 0.30.0 | driver | Async Postgres. **The URL must say `+asyncpg`** |
| **Pydantic v2** | 2.13.4 | `app/schemas/` | Request/response DTOs + validation |
| **pydantic-settings** | 2.14.2 | `app/core/config.py` | Env-driven config, one place |
| **email-validator** | 2.2.0 | — | Backs Pydantic's `EmailStr` |
| **Celery** | 5.6.3 | `app/scheduler/` | Nightly pipeline. Chosen over APScheduler (decided in spec) |
| **redis** | 8.0.1 | `app/scheduler/locks.py` | Broker **and** the per-user run lock |
| **httpx** | 0.28.1 | providers, LLM, Telegram | One async HTTP client for every outbound call. Injectable → tests swap in a `MockTransport` |
| **PyJWT** | 2.10.1 | `app/core/security.py` | Access + refresh tokens |
| **passlib + bcrypt** | 1.7.4 / **4.0.1** | `app/core/security.py` | Password hashing via `bcrypt_sha256` (no 72-byte limit). **bcrypt pinned to 4.0.1** — passlib 1.7.4 reads `bcrypt.__about__`, removed in 4.1+ |
| **cryptography** | 46.0.7 | `app/core/crypto.py` | Fernet — encrypts your stored API keys |
| **python-multipart** | 0.0.20 | résumé upload | Multipart form parsing |
| **tenacity** | 9.0.0 | available | Retry helper |

Dev-only: `pytest`, `pytest-asyncio`, `aiosqlite` (tests run on in-memory SQLite — **no Postgres
needed to run the suite**), `ruff`, `isort`, `black`, `mypy`.

### 5.2 Frontend

| Library | Version | Where | Why |
|---|---|---|---|
| **Angular** | **19.2** | everywhere | Standalone components + signals. **Pinned — see §2** |
| **Angular Material** | 19.2 | all UI | Component kit + the theme system |
| **Angular CDK** | 19.2 | — | Material's foundation |
| **Tailwind CSS** | 3.4 | layout/spacing | Utility classes. **Preflight is OFF** so it doesn't fight Material's reset |
| **RxJS** | 7.8 | HTTP, interceptor | The refresh-queueing logic |
| **AG Grid Community** | 33.3 | `features/matches/` | Sortable/filterable match table |
| **ApexCharts + ng-apexcharts** | 5.16 / **1.15.0** | `features/dashboard/` | Run-result chart. **1.15.0 pinned** — 2.x needs Angular ≥20 |
| **ngx-translate** | 16 | `layout/shell` | i18n, loads `public/i18n/en.json` |
| **Vitest + AnalogJS + jsdom** | / 1.22.5 / **25** | `*.spec.ts` | Tests. Angular 19 has **no first-party Vitest builder** (that's Angular 20+), so AnalogJS is the supported route. jsdom = **no Chrome needed** |

---

## 6. Component walkthrough

```
backend/app/
├── main.py                 create_app() — the FastAPI factory
├── core/
│   ├── config.py           EVERY env var, one place (§3.2)
│   ├── security.py         password hashing + JWT create/decode
│   ├── crypto.py           Fernet encrypt/decrypt/mask for stored keys
│   └── exceptions.py       AppError → {detail, code} JSON. Services raise these,
│                           NEVER HTTPException (keeps business logic HTTP-free)
├── api/
│   ├── deps.py             get_db · get_current_user · require_admin ·
│   │                       get_http_client (injectable ⇒ tests mock the network)
│   └── v1/routes/          auth · profiles · searches · resumes · matching ·
│                           ingestion · pipeline · credentials · settings · providers
├── models/                 15 SQLAlchemy tables + enums.py
├── schemas/                Pydantic DTOs (the API's contract)
├── repositories/           SQLAlchemy. The ONLY layer that touches a session
├── services/
│   ├── ingestion.py        search → normalize → expiry → dedup → store
│   ├── matching.py         score + eligibility + optional LLM explanation
│   ├── notification.py     THE §7 RULES LIVE HERE: top-20 cap, no minimum,
│   │                       never repeat, actionable-first
│   ├── pipeline.py         chains the three — used by BOTH the HTTP trigger
│   │                       and the Celery task, so they can't drift
│   ├── credential.py       encrypt on write, mask on read
│   └── profile.py, settings.py, provider.py, search.py, resume.py
├── matching/
│   ├── scoring.py          ⭐ the weighted score. Pure. No I/O. No AI.
│   ├── eligibility.py      ⭐ the work-auth gate. Pure.
│   └── llm.py              Anthropic + OpenAI behind one port
├── providers/
│   ├── base.py             the JobProvider contract
│   ├── registry.py         which providers are enabled for THIS user
│   ├── catalog.py          the 8 providers + what keys each needs
│   ├── salary.py           ⭐ INR → LPA. Pure.
│   ├── dedup.py            ⭐ URL → stable dedup key. Pure.
│   └── adapters/           the 8 job-board clients
├── notifications/          telegram.py · email.py (behind a Notifier port)
└── scheduler/
    ├── celery_app.py       beat schedule: 03:00 UTC daily
    ├── locks.py            per-user Redis lock (compare-and-delete release)
    └── tasks.py            asyncio.run(...) bridge — Celery is sync, services are async
```

⭐ = pure domain logic. No database, no network, no framework. Directly unit-testable, and that's
where the highest-value tests live.

```
frontend/src/app/
├── core/
│   ├── models/api.models.ts        TS mirrors of the backend DTOs
│   ├── services/api.service.ts     ONE typed client for the whole backend
│   ├── services/auth.service.ts    tokens (signals) + login/register/refresh
│   ├── services/theme.service.ts   dark mode (default) — one class on <html>
│   ├── interceptors/auth.interceptor.ts   JWT + the refresh queue
│   └── guards/auth.guard.ts        authGuard · guestGuard · adminGuard
├── layout/shell.component.*        sidenav + toolbar + theme toggle
└── features/                       lazy-loaded, one folder each
    ├── auth/          login + register (first account ⇒ Admin)
    ├── dashboard/     profile picker, daily/catch-up run, ApexCharts, provider health
    ├── matches/       AG Grid — score, band, eligibility, apply link
    ├── profiles/      create/delete, skills, gate
    ├── providers/     health + admin-only enable/disable
    ├── settings/      LLM provider/model, Telegram/email, encrypted API keys
    └── admin/         user list (admin only)
```

---

## 7. Connecting AI

### 7.1 What the AI does — and what it is *not allowed* to do

| ✅ It does | ❌ It never does |
|---|---|
| Explains a score in plain English | **Produce or change the score** |
| Tailors a résumé to a role | Invent experience you don't have |
| | Decide what qualifies |

The score is computed by `matching/scoring.py` — arithmetic, deterministic, reproducible. The LLM
is handed a score that *already exists* and asked to explain it. This is enforced in the prompt
and by the call order (score first, then optionally explain).

**No key = the app still works.** You lose explanations and tailoring. You lose nothing else.

### 7.2 Wiring it up

1. Get a key — [Anthropic console](https://console.anthropic.com/) or
   [OpenAI platform](https://platform.openai.com/api-keys).
2. In the app: **Settings**
   - **LLM provider** → `Anthropic` or `OpenAI`
   - **Model** → leave blank for the default, or name one
   - **Save settings**
3. Still in Settings, under **API keys**: key = `llm_api_key`, value = your key → **Store key**.

It's encrypted immediately. Reload the page and you'll see `****` + the last 4 characters — the
plaintext never comes back to the browser.

### 7.3 Defaults and the one gotcha

| Provider | Default model | Endpoint |
|---|---|---|
| Anthropic | `claude-opus-4-8` | `POST https://api.anthropic.com/v1/messages` |
| OpenAI | `gpt-4o-mini` | `POST https://api.openai.com/v1/chat/completions` |

> ### ⚠️ Do not add `temperature` to the Anthropic call
>
> `matching/llm.py` deliberately sends **no `temperature` and no `top_p`**. Current Anthropic
> models (Opus 4.8) **reject those parameters with a 400**. The reflex to "set temperature=0 for
> determinism" will break every AI call in this app. There's a comment in the file saying so.
> Determinism isn't needed anyway — the *score* is already deterministic; the LLM only writes prose.

Headers used: `x-api-key` + `anthropic-version: 2023-06-01`. A `stop_reason: "refusal"` comes back
as HTTP 200 with no usable text — the client treats that as "no output" and degrades gracefully.

### 7.4 Cost control

Explanations are generated only for matches that **cleared the gate**, capped by your
`notify_cap` (default 20). A run that produces 4 matches makes 4 LLM calls. If the LLM errors, the
match is still stored — you just don't get prose.

---

## 8. Job providers & their keys

| Provider | Credential key(s) | Get it from | Notes |
|---|---|---|---|
| **Remotive** | *none* | — | Works instantly. **But:** their API currently **ignores the `search` param** and only exposes ~39 jobs total. Fine for a smoke test, weak as a real source. |
| **Greenhouse / Lever** | *none* | — | Company ATS boards. You supply board tokens in the search params: `{"greenhouse_boards": ["stripe","databricks"], "lever_boards": ["…"]}`. **Highest source-quality score (100)** — it's the company's own board. |
| **Adzuna** | `adzuna_app_id`, `adzuna_app_key` | [developer.adzuna.com](https://developer.adzuna.com/) | Defaults to the India board |
| **Jooble** | `jooble_key` | [jooble.org/api/about](https://jooble.org/api/about) | |
| **JSearch** | `rapidapi_key` | [RapidAPI → JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | |
| **Google Jobs** | `serpapi_key` | [serpapi.com](https://serpapi.com/) | |
| **LinkedIn** | `apify_token` | [Apify console](https://console.apify.com/account/integrations) | Actor `fantastic-jobs/advanced-linkedin-job-search-api`. **This is where the real volume is.** |
| **Naukri** | `apify_token` | same token | Actor `muhammetakkurtt/naukri-job-scraper` |

A provider is enabled **only if** it's active in the catalog **and** all its keys are stored. One
provider timing out is retried once, marked unhealthy, and the run continues without it.

### Query recipes that actually work

Saved searches carry a free-form `params` blob passed to the adapter.

**LinkedIn (Apify)** — broad titles + tech-in-description massively out-performs narrow queries:

```json
{
  "titleSearch": ["Backend Engineer", "Backend Developer", "Python Developer", "Software Engineer"],
  "descriptionSearch": ["Python", "FastAPI"],
  "locationSearch": ["India"],
  "aiExperienceLevelFilter": ["2-5"],
  "removeAgency": true,
  "populateExternalApplyURL": true,
  "limit": 100
}
```

**Naukri** — search `"FastAPI Backend Developer"`, **never bare `"Python"`** (that floods you with
AI/ML-trainer and data-science roles).

**Greenhouse** — target companies directly:

```json
{ "greenhouse_boards": ["stripe", "databricks", "cloudflare"], "limit": 500 }
```

---

## 9. Using the app day to day

### First run

1. `docker compose up -d --build` → open **http://localhost:8080**
2. **Register.** The first account ever created becomes **Admin**.
3. **Profiles → create one.** Skills are **40% of the score** — a profile with no skills can
   match nothing. Set your experience band and locations.
4. **Add a saved search** (Remotive needs no key, so you can run immediately).
5. **Settings** → add provider keys, and an LLM key if you want explanations.
6. **Dashboard** → pick the profile → **Run pipeline** (Daily = 24h, Catch-up = 7d).

### After that

It runs itself nightly at **03:00 UTC** and pushes the top ≤20 fresh matches to Telegram/email.
You open **Matches** when you want the full table.

### Reading a match

| Field | What it means |
|---|---|
| **Score / band** | ≥90 only. 95+ High, 92–94 Medium-High, 90–91 Stretch |
| **Eligibility** | `actionable` = apply now · `gated` = ask the recruiter about sponsorship first |
| **Breakdown** | Per-dimension scores. A missing `experience` key means *the posting never stated it* — not that it scored zero |
| **Missing skills** | What the posting wants that you didn't list |

---

## 10. Deployment

### Standard

```bash
cp .env.example .env      # fill the two secrets
docker compose up -d --build
docker compose logs -f api
```

| Port | Service |
|---|---|
| 8080 | Nginx → the app |
| 8000 | API directly (`/docs`) |

### Why Nginx, and why no CORS layer

The SPA calls `/api/v1/...` — a **relative** path. Nginx serves the SPA *and* proxies `/api` to the
API, so the browser only ever sees one origin. Same in dev (`ng serve` proxies via
`proxy.conf.json`). **That's why the backend has no CORS middleware — it never needs one.**

Nginx also falls back to `index.html` for unknown paths, otherwise refreshing on `/matches` would
404. Hashed assets are cached for a year; `index.html` is `no-store` so a deploy isn't pinned to a
stale bundle.

### Operating

```bash
docker compose ps                       # health of all 6
docker compose logs -f worker           # what the pipeline is doing
docker compose exec api alembic current # applied migration
docker compose down                     # stop (volumes survive)
docker compose down -v                  # ⚠️ DESTROYS the database
```

### Backups

```bash
# Backup
docker compose exec -T postgres pg_dump -U ajh ajh > backup.sql

# Restore
docker compose exec -T postgres psql -U ajh -d ajh < backup.sql
```

> **A database backup is useless without the same `CREDENTIALS_ENCRYPTION_KEY`.** The stored API
> keys are ciphertext. Back the key up separately, somewhere the database dump isn't.

### Exposing it to the internet

This was built for personal use and is **not hardened for the public internet**. If you must:

- Put a real TLS terminator in front (Caddy/Traefik, or Nginx + certbot)
- Don't publish port 8000 (drop the `ports:` block on `api` — Nginx reaches it on the internal network)
- Registration is **open** — the first user is Admin, but anyone who finds the URL can sign up.
  Restrict at the proxy, or change the register route to admin-only.

---

## 11. Making changes

### Add a job provider

1. `backend/app/providers/adapters/yourboard.py` — subclass `JobProvider`, implement
   `search_jobs()` and `normalize()`.
2. Add the slug to `models/enums.py::ProviderSlug` and any new key to `CredentialKey`.
3. Register it in `providers/catalog.py` (display name + required keys) and
   `providers/registry.py::PROVIDER_CLASSES`.
4. **Migration** — the enum is a `VARCHAR + CHECK`, so a new value needs one:
   `alembic revision --autogenerate -m "add yourboard provider"`.
5. Test it with an httpx `MockTransport` (copy `tests/test_ingestion.py`).

Nothing else changes. The registry, pipeline, and UI pick it up.

### Change how scoring works

Everything lives in **`backend/app/matching/scoring.py`** — pure, no I/O.

- **Weights:** don't edit code. They're **per-profile** (`profiles.scoring_weights`), editable
  through the API.
- **The gate:** also per-profile (`profiles.min_score`, default 90).
- **A new dimension:** add it to `ScoreInput` + `components`, give it a weight key, update
  `DEFAULT_SCORING_WEIGHTS`, and add tests in `tests/test_matching_domain.py`.

> **Rule:** if a dimension can't be assessed, **drop it and renormalize** — never invent a
> "neutral" number. That's what created the unreachable-gate bug (§4.5).

### Change the database

```bash
cd backend
# 1. edit app/models/*.py
alembic revision --autogenerate -m "what changed"   # 2. review the generated file!
alembic upgrade head                                # 3. apply
alembic check                                       # 4. must say "no new upgrade operations"
```

CI runs `alembic check` — a model edited without a migration **fails the build**.

### Add a screen

1. `frontend/src/app/features/yourthing/yourthing.component.ts` (standalone).
2. Add a lazy route in `app.routes.ts` (inside the shell's `children`).
3. Add a nav entry in `layout/shell.component.ts` (+ an i18n key in `public/i18n/en.json`).
4. Call the backend through `ApiService` — don't inject `HttpClient` into components.

### Add an API endpoint

Respect the layering, or the tests will get hard to write:

```
route (app/api/v1/routes/)      ← HTTP only. No logic.
  └── service (app/services/)   ← the use-case. Owns the transaction.
        └── repository (app/repositories/)  ← the only place with a session
              └── model (app/models/)
```

Raise `AppError` subclasses from services — never `HTTPException`. The handler in
`core/exceptions.py` turns them into `{detail, code}` JSON.

---

## 12. Testing

```bash
cd backend  && pytest -q        # 86 tests — no database needed (in-memory SQLite)
cd frontend && npm test         # 19 tests — Vitest + jsdom, no browser needed
```

**How the tests avoid the network:** `get_http_client` is an injectable FastAPI dependency. Tests
override it with an httpx `MockTransport`, so the whole pipeline — providers, Telegram, everything
— runs offline and deterministically.

The highest-value tests are the pure-domain ones (`test_matching_domain.py`,
`test_providers_domain.py`): scoring, the work-auth gate, INR→LPA parsing, dedup keys. They're fast
and they're where the real rules live.

Lint gates (identical to CI):

```bash
cd backend && ruff check app tests && isort --check-only app tests && black --check --line-length 100 app tests
```

---

## 13. Troubleshooting

### "The run found 0 matches" — usually correct, not a bug

This is the single most likely thing to confuse you, so:

The gate is **90**, and tech-stack is **40%** of it. To clear 90 you essentially need the posting
to want *most of your listed skills*. In a real run against Stripe + Databricks + Cloudflare
(251 real jobs), **zero** qualified — because those companies don't ask for FastAPI. The system was
working correctly; it refused to pad the list.

Work through this in order:

| Check | Fix |
|---|---|
| Does the profile have skills? | No skills ⇒ nothing can ever score. Add them. |
| Are your skills *too* specific? | Listing `FastAPI` as required when most JDs say "Python" will reject nearly everything. Drop rare skills, or lower `min_score`. |
| Is the source any good? | Remotive exposes ~39 jobs and ignores search. **Real volume comes from LinkedIn/Naukri via Apify.** |
| Look at `below_gate` in the run summary | It's honest. If it's 251, the jobs were fetched and genuinely didn't fit. |
| Inspect a breakdown | `GET /profiles/{id}/matches` shows `component_scores`. Low `tech_stack` = wrong jobs, not a broken scorer. |

**Lower the gate to see what's near-miss:** set the profile's `min_score` to 75 temporarily. If
75-85s appear, the pipeline is healthy and your skills/sources need tuning.

### Other things

| Symptom | Cause / fix |
|---|---|
| Compose exits: `set SECRET_KEY in .env` | Working as designed. Fill in `.env` (§3.1). |
| `401` on every request | Access token expired and the refresh failed → sign in again. |
| Stored API key stopped working | Did `CREDENTIALS_ENCRYPTION_KEY` change? Old ciphertext is unreadable. Re-enter the keys. |
| A provider shows `unhealthy` | Missing/invalid key, or their API is down. The run continues without it — by design. |
| Frontend 404s on refresh | Nginx `try_files` fallback — only bites if you're serving `dist/` with something other than the shipped config. |
| `npm install` fights you | The Angular 19 pin (§2). Don't `npm update` blindly. |
| Migration conflict | `alembic history`, then `alembic upgrade head`. CI's `alembic check` should have caught it. |

---

## 14. Known gaps & honest status

**Verified working** (I ran this, it isn't theory):

- Full pipeline against the **live Remotive API** and **live Greenhouse boards** (1,548 real jobs
  fetched from Stripe/Databricks/Cloudflare in 3.3s → 251 unique after dedup).
- Register → Admin, profiles, skills, saved searches, scoring, dedup-on-rerun (0 new on the second
  run), credential encryption (plaintext never returned), provider catalog + RBAC.
- 86 backend + 19 frontend tests. Lint clean. `alembic check` clean.

**Specced but NOT implemented** — don't be surprised:

| Gap | Status |
|---|---|
| **Résumé text extraction** | Upload + parse-status work. Nothing actually reads the PDF/DOCX/LaTeX. `content_text` stays null. |
| **Résumé tailoring endpoint** | The LLM client and prompt exist. No route wires them together. |
| **Applications tracker UI** | Table + model exist. No screen. |
| **Analytics screen** | Not built. |

**Not verified:**

| Thing | Why |
|---|---|
| **The Docker images have never been built** | The Docker daemon was unresponsive on the build machine (`docker build` hangs; `docker compose config` validates because it never contacts the engine). Compose is schema-valid only. **Your `docker compose up --build` is the first real build.** If the backend image fails, suspect a wheel missing for `linux/amd64` on Python 3.12 — local dev ran 3.13. |
| **The UI was never clicked through** | No browser automation available. Components are unit-tested and the API is verified end-to-end, but nobody has visually driven the screens. |

**Bugs found by actually running it** (both fixed, both regression-tested):

1. **The gate was mathematically unreachable** for any posting that didn't state years of
   experience — a perfect match scored 89 against a gate of 90. Caused by scoring "unknown" as a
   neutral 70. Now the dimension is dropped and weights renormalize.
2. **The JWT interceptor logged you out on a failed *login*** — navigating away and wiping the
   "Incorrect email or password" message you needed to read. It also called `logout()` twice on a
   failed refresh.
