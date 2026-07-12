# AJH — AI Job Hunter Platform · Master Spec (v2, FINAL)

> **Single source of truth.** Supersedes the original project description. All contradictions
> were discussed and resolved with the owner (Dheerendra) on 2026-07-10.
> If any new requirement is unclear, STOP and ask — never assume, never hallucinate.

---

## 1. Role & Objective

Act as an AI recruiter + job-hunting engine. Find currently-open roles that genuinely fit
the candidate, score them honestly, tailor a defensible résumé per role, and track everything.
Optimize for interviews that convert, not vanity metrics. **A smaller list of true fits beats
a padded list of stretches.**

Scope: personal use for the owner and a few friends. Multi-user, but NOT full SaaS hardening
(no payments, GDPR tooling, or heavy observability for now).

---

## 2. Technology Stack

**Frontend:** Angular (pin latest stable at Phase 9 start), TypeScript strict, Angular Material,
Tailwind CSS, RxJS, Signals, Standalone Components, Reactive Forms, Router, HTTP Interceptors,
Route Guards, CDK, ngx-translate, ApexCharts, AG Grid Community. Dark mode required.

**Backend:** Python 3.12+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis,
**Celery + Redis** (NOT APScheduler — decided), Pydantic v2.

**AI engine (decided):** rule-based deterministic weighted scoring (see §7); LLM
(Anthropic/OpenAI — user provides API key in Settings) used ONLY for match explanations and
per-role résumé tailoring. No LLM key → scoring still works, tailoring/explanations disabled.

**Infra:** Docker, Docker Compose, Nginx, GitHub Actions. Claude writes configs; owner runs
Docker manually on his machine (sandbox cannot run Docker).

---

## 3. Architecture Rules

Clean Architecture — Presentation / Application / Domain / Infrastructure.
No business logic in controllers/components. SOLID, Repository Pattern, Service Layer, DTOs,
DI, async where appropriate.

**Frontend structure:** `src/app/{core, shared, layout, auth, dashboard, jobs, profiles, resumes, providers, analytics, applications, notifications, settings, admin, ai, store, services, guards, interceptors, directives, pipes, models, utils}` — lazy-loaded feature routes.

**Backend structure:** `backend/app/{api, auth, users, profiles, jobs, providers, matching, resumes, applications, notifications, analytics, scheduler, admin, services, repositories, models, schemas, database, core, tests}`.

---

## 4. Candidate Profiles (fully configurable — nothing profession-hardcoded)

Everything candidate-specific lives in per-profile config, seeded with the owner's defaults:
unlimited skills, unlimited target roles, preferred/ignored companies, certifications,
languages, multiple resumes, experience band, locations, work modes, scoring weights,
query recipes / saved search templates.

**Empty states:** if a profile lacks resume/skills/providers, ASK the user first — do not run
a pipeline on an empty profile.

---

## 5. Job Providers

Pluggable provider interface: `search_jobs()`, `normalize()`, `health_check()`.

**Free/API providers (always available):** Adzuna, Jooble, JSearch (RapidAPI), Remotive,
Greenhouse & Lever boards, Google Jobs via SerpAPI.
**Wellfound: DROPPED** — US-centric, remote roles exclude India.

**Apify connector (enabled when user supplies an Apify API key in Settings):**
Backend calls Apify **REST API directly** with the user's key (the "MCP-only / REST blocked"
constraint applied to Claude chat sessions, not to this backend — resolved).

- **LinkedIn:** actor `fantastic-jobs/advanced-linkedin-job-search-api` — supports
  `datePostedAfter`, `titleSearch`, `descriptionSearch`, `locationSearch`,
  `aiExperienceLevelFilter`, `removeAgency`, `populateExternalApplyURL`; exposes
  `org_linkedin_size`, `org_linkedin_headcount`, `date_valid_through`, `recruiter_name`,
  `ai_visa_sponsorship`.
- **Naukri:** actor `muhammetakkurtt/naukri-job-scraper` — `keyword`, `experience`,
  `freshness`, `sortBy:date`, `maxJobs` (min 50).
- Indeed and others may be added later via additional Apify actors.

**Proven LinkedIn query recipe (ships as the owner's default saved search template):**

- `titleSearch`: ["Backend Engineer","Backend Developer","Python Developer","Software Engineer","Software Developer"]
- `descriptionSearch`: ["Python","FastAPI"] — broad-title + tech-in-description combo massively
  out-performs narrow queries.
- `locationSearch`: ["India"] · `aiExperienceLevelFilter`: ["2-5"] · `removeAgency`: true ·
  `populateExternalApplyURL`: true · `limit`: 100.
- Daily mode: `datePostedAfter` = last 24 h. Catch-up: last 3–7 days.

**Portal-tuning learnings:**

- Naukri: search "FastAPI Backend Developer" / "Python Backend Developer" — NEVER bare
  "Python" (floods with AI/ML-trainer and data-science roles).
- Big enterprises dominate raw volume (Infosys, TCS, Accenture, Cognizant, Qualcomm…).
  Company-owned portals (IBM, Deloitte USI, PwC, Siemens) are not fully indexed by LinkedIn
  scrapers — search directly when targeting a specific brand.

**Provider failures:** basic checks only — timeout, retry-once, mark provider unhealthy,
continue pipeline with remaining providers. No circuit-breaker complexity.

---

## 6. Deduplication (RESOLVED: simple, not fuzzy)

- Persistent DB store of every job ever shown, keyed on **listing URL/ID**. Never rely on
  session memory.
- Collapse multi-city/repost duplicates (same role + company) to one best direct link.
- Each run returns ONLY new listings.
- NO fuzzy cross-portal matching (explicitly descoped).
- Drop expired/closed listings on each pass.

**Expiry check (best effort):** use `date_valid_through` where the provider gives it;
HTTP-check Greenhouse/Lever apply URLs before storing; providers with neither field are
best-effort — some expired jobs may slip through (accepted).

---

## 7. Scoring (0–100) — with integrity rule

Weights (per-profile configurable; owner's defaults):

| Dimension                                       | Weight |
| ----------------------------------------------- | ------ |
| Tech-stack match (Python + FastAPI + Mongo/SQL) | 40     |
| Experience match (2–5 yrs)                     | 20     |
| Role match (backend/API/platform)               | 20     |
| Domain/company fit                              | 10     |
| Source quality + direct-apply trust             | 10     |

Bands: 95–100 High · 92–94 Medium-High · 90–91 Stretch. **Gate at ≥90.**

Output per match: score, explanation, strengths, missing skills, recommendation,
suggested/tailored resume.

**Integrity rules (hard):**

- NEVER inflate a score to reach a target count. If a run yields 6 qualified, report 6 and
  explain what excluded the rest. Accuracy over quantity.
- Reality: a fresh window normally yields 4–10 genuine ≥90 matches; >95 appears ~1–2×/week.
- **Notifications: cap = top 20 fresh matches per run, NO minimum.** Never repeat
  previously-notified jobs.

---

## 8. Work-Authorization Logic (critical)

- India-based or India-eligible-remote roles → actionable now (no sponsorship needed).
- Offshore roles (Ukraine, Romania, Canada, EU, US…): candidate willing to relocate but NOT
  work-authorized; most postings state no sponsorship → flag **"eligibility-gated"**, not
  qualified, UNLESS posting explicitly offers sponsorship/relocation.
- NEVER advise answering "Yes, I am legally eligible" when untrue — false declaration.
- OFAC/sanctions question: India is not embargoed → "No".
- Willingness ≠ eligibility. Raise the eligibility question to the recruiter; don't let it
  silently sink an application, and don't spend energy on walls that won't move.

**Location strategy:** priority = India (all locations; remote/office/hybrid). For remote,
search worldwide — but global-remote roles excluding India or requiring sponsorship are
eligibility-gated per above (so worldwide search yields fewer actionable results; expected).

---

## 9. Company-Size / Selection-Odds Mode (optional toggle)

Filter by `org_linkedin_headcount`: small (≤200) / mid (≤500) → candidate is a top-few
applicant, recruiters read résumés directly, faster cycles, less ATS gatekeeping. Prioritize
these + named-recruiter + direct-apply + "immediate joiner" roles.
Honest trade-off: narrowing shrinks the pool — cannot also demand 20+/run. 4 roles where
you're top-3 beat 20 where you're 1-of-500.

---

## 10. Salary (RESOLVED)

Display salaries **raw as posted**. Compute LPA **only for INR postings**. No FX conversion.
Parse "₹15 LPA", monthly INR, and ranges into LPA where possible; "competitive"/absent → null.

---

## 11. Resumes

- Upload formats: PDF, DOCX, LaTeX only. Multi-upload supported.
- Parsing failures on scanned/exotic files: report clearly, don't crash.
- Per-role tailored résumé generated by LLM (requires user's LLM key), must stay
  **defensible** — no fabricated experience.

---

## 12. Auth & Users (TRIMMED for personal use)

- **Email + JWT only.** Google/GitHub OAuth deferred.
- RBAC: Admin, User.
- Include refresh tokens; skip email-verification/password-reset flows for now (personal use).

---

## 13. Notifications (TRIMMED)

- **Telegram + Email only.** Slack/Discord deferred.
- Per run: top-20 cap, fresh-only, no repeats (see §7).

---

## 14. Scheduler Pipeline (Celery + Redis)

Search → Normalize → Expiry-check → Deduplicate → AI Match → Store → Notify.
Per-user locking so concurrent runs for the same user don't overlap.
Daily mode (24 h window) + manual catch-up mode (3–7 days).

---

## 15. Database (PostgreSQL + Alembic)

Normalized tables: users, profiles, skills, profile_skills, resumes, jobs, job_skills,
providers, applications, notifications, settings, searches — plus `seen_jobs` (dedup store)
and provider credentials (encrypted API keys: Apify, LLM, SerpAPI, RapidAPI, Adzuna, Jooble).

---

## 16. REST API

Versioned (`/api/v1`), OpenAPI docs, pagination, filtering, sorting, validation, JWT auth.

---

## 17. Testing / Standards / Docs / Deployment

- Backend: pytest + integration + API tests. Frontend: Vitest, component tests.
- Backend lint: Black, Ruff, isort, mypy. Frontend: ESLint, Prettier.
- Docs: README, Mermaid architecture diagrams, ER diagram, API docs, deployment guide.
- Deployment: Dockerfiles, docker-compose, GitHub Actions, .env examples.

**Angular build policy (decided — option c):** Claude generates code continuously; runs
sandbox `ng build` compile-checks only at phase gates. Owner runs `ng serve` locally for
iterative dev.

---

## 18. Build Plan (never generate the whole app at once)

1. Architecture · 2. Database · 3. Authentication · 4. Backend APIs ·
2. Job Provider Framework · 6. AI Matching · 7. Scheduler · 8. Notifications ·
3. Angular Frontend · 10. Testing · 11. Deployment · 12. Documentation

After each phase: verify compilation, verify tests, explain architecture decisions,
**wait for owner approval before continuing**. Never skip files, APIs, tests, or docs.

**Session-resume protocol:** `PROGRESS.md` tracks phase status, decisions, and next steps.
At the start of every new session, read `CLAUDE.md` + `PROGRESS.md` first.
