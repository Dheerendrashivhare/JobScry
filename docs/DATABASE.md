# AJH Database (Phase 2)

PostgreSQL + SQLAlchemy 2.0 (async) + Alembic. Schema covers every table in
CLAUDE.md §15 plus a `matches` table for scored results (needed by the pipeline in
§14). Enum columns are stored as `VARCHAR + CHECK` with lowercase values; JSON
columns hold list/dict config that §15 does not call out as its own table.

## ER diagram

```mermaid
erDiagram
    users ||--o{ profiles : owns
    users ||--o| settings : has
    users ||--o{ credentials : has
    users ||--o{ notifications : receives

    profiles ||--o{ profile_skills : declares
    skills   ||--o{ profile_skills : used_in
    profiles ||--o{ resumes : has
    profiles ||--o{ searches : has
    profiles ||--o{ matches : scored_in
    profiles ||--o{ applications : tracks
    profiles ||--o{ seen_jobs : dedups
    profiles ||--o{ notifications : about

    jobs ||--o{ job_skills : tagged
    skills ||--o{ job_skills : used_in
    jobs ||--o{ matches : scored_in
    jobs ||--o{ applications : applied_to
    jobs ||--o{ seen_jobs : recorded_as

    matches }o--o| resumes : tailored_resume
    applications }o--o| resumes : used_resume

    users {
        int id PK
        string email UK
        string hashed_password
        string full_name
        enum role "admin|user"
        bool is_active
    }
    profiles {
        int id PK
        int user_id FK
        string name
        bool is_default
        int experience_min_years
        int experience_max_years
        json target_roles
        json preferred_companies
        json ignored_companies
        json certifications
        json languages
        json locations
        json work_modes
        json scoring_weights
        int min_score "gate, default 90"
        bool company_size_mode
        int max_headcount
    }
    skills {
        int id PK
        string name UK
    }
    profile_skills {
        int id PK
        int profile_id FK
        int skill_id FK
        float weight
        bool is_required
        string proficiency
    }
    resumes {
        int id PK
        int profile_id FK
        string filename
        enum format "pdf|docx|latex"
        string storage_path
        text content_text
        enum parse_status
        bool is_primary
    }
    jobs {
        int id PK
        string dedup_key UK "listing URL/ID"
        enum provider_slug
        string external_id
        string url
        string apply_url
        string title
        string company
        text description
        string location
        bool is_remote
        enum work_mode
        int company_headcount
        string recruiter_name
        string salary_raw
        string salary_currency
        numeric salary_lpa_min
        numeric salary_lpa_max
        bool visa_sponsorship
        datetime posted_at
        datetime valid_through
        bool is_expired
        json raw_payload
    }
    job_skills {
        int id PK
        int job_id FK
        int skill_id FK
    }
    matches {
        int id PK
        int profile_id FK
        int job_id FK
        int score "0-100"
        enum band "high|medium_high|stretch"
        enum eligibility_status
        json component_scores
        text explanation
        json strengths
        json missing_skills
        text recommendation
        int tailored_resume_id FK
        bool notified
    }
    seen_jobs {
        int id PK
        int profile_id FK
        string dedup_key
        int job_id FK
        datetime first_seen_at
        datetime notified_at
    }
    providers {
        int id PK
        enum slug UK
        string display_name
        json requires_credentials
        bool is_apify
        bool is_active
        enum last_health_status
        datetime last_checked_at
    }
    credentials {
        int id PK
        int user_id FK
        enum key
        text encrypted_value "Fernet ciphertext"
    }
    settings {
        int id PK
        int user_id FK "unique"
        enum llm_provider
        bool telegram_enabled
        string telegram_chat_id
        bool email_enabled
        string notify_email
        string smtp_host
        int smtp_port
        string smtp_username
        int notify_cap "default 20"
        string locale
        string theme "default dark"
    }
    searches {
        int id PK
        int profile_id FK
        string name
        enum provider_slug "null = all"
        enum mode "daily|catchup"
        bool is_active
        json params "query recipe"
        datetime last_run_at
    }
    applications {
        int id PK
        int profile_id FK
        int job_id FK
        int resume_id FK
        enum status
        enum eligibility_status
        datetime applied_at
        string external_reference
        text notes
    }
    notifications {
        int id PK
        int user_id FK
        int profile_id FK
        enum channel "telegram|email"
        enum status
        string subject
        text body
        json payload "included match ids"
        datetime sent_at
        text error
    }
```

## Table notes

| Table | Purpose | Spec |
|---|---|---|
| `users` | Accounts + RBAC (admin/user) | §12 |
| `profiles` | All candidate-specific config; skills normalized, the rest in JSON | §4 |
| `skills` / `profile_skills` | Canonical skill vocabulary; the join carries scoring weight | §4, §7 |
| `resumes` | PDF/DOCX/LaTeX uploads, parse status, per-profile | §11 |
| `jobs` | Global normalized listing catalog, unique on `dedup_key` | §5, §6 |
| `job_skills` | Skills extracted from a posting (shared `skills` vocab) | §15 |
| `matches` | Scored (profile, job) result: score, band, breakdown, LLM enrichment | §7 |
| `seen_jobs` | Per-profile dedup store — every listing ever shown, keyed on URL/ID | §6 |
| `providers` | Provider catalog + best-effort health | §5 |
| `credentials` | Per-user encrypted API keys (Fernet), one row per (user, key) | §15 |
| `settings` | Per-user notification/LLM/UI preferences (secrets stay in `credentials`) | §13 |
| `searches` | Saved search templates / query recipes (opaque `params` JSON) | §4, §5 |
| `applications` | Application lifecycle tracking, carries eligibility | §8 |
| `notifications` | Delivery log (Telegram/Email), records bundled match ids | §7, §13 |

## Design decisions

- **Enums as `VARCHAR + CHECK`** (`native_enum=False`, `values_callable`) — portable
  (Postgres + SQLite), migration-friendly (no native-type ALTER dance), stores
  readable lowercase values that match Pydantic serialization.
- **JSON for list-like profile config** — CLAUDE.md §15 names only `skills` as a
  normalized child; target roles, companies, locations, weights, etc. live in JSON
  columns on `profiles`, avoiding a dozen thin join tables.
- **`jobs` global vs `seen_jobs`/`matches` per-profile** — the catalog is deduped
  once on `dedup_key`; "already shown" and "scored" state is per-profile.
- **Secrets isolated in `credentials`** — encrypted at rest; `settings` and
  `providers` hold only non-secret config.
- **Lazy engine/session** — building the engine is deferred to first use so importing
  models needs no DB driver (keeps model tests driver-free).
- **Deterministic constraint names** via a metadata naming convention → stable,
  reviewable Alembic autogenerate output.

## Migrations

See `backend/alembic/README.md`. Apply to a fresh Postgres with `alembic upgrade
head`. The initial migration (`initial schema`) creates all 15 tables and was
verified with a full upgrade→downgrade round-trip.
