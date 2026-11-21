# Joby — Architecture

AI agent that finds job opportunities, tailors a CV per offer, and applies on the user's behalf. Built for personal use first, designed to become a multi-tenant SaaS.

Status: v1 design · Last updated: 2026-11-08 (auth → NestJS JWT)

---

## 1. Decisions

| # | Area | Decision | Rationale |
|---|---|---|---|
| D1 | Frontend | React + Vite SPA, TanStack Router + Query, Tailwind + shadcn/ui | App lives behind auth; no SSR needed |
| D2 | Product API | NestJS (TypeScript) | Modules, DI, guards; owner of all product data |
| D3 | Agent service | Python, FastAPI, LangGraph | Multi-agent graphs, checkpointing, interrupts |
| D4 | Nest ↔ Python | HTTP/JSON (REST + signed callbacks) | Simple, debuggable, no broker. gRPC reconsidered later |
| D5 | Database | PostgreSQL 16 + pgvector | Relational SaaS data, JSONB, embeddings, `SKIP LOCKED` queue, LangGraph checkpointer |
| D6 | Nest ORM | Prisma | Typed client, migrations |
| D7 | Python DB access | SQLAlchemy 2.0 (async) + Alembic, own schema | Python service owns its tables |
| D8 | Job execution | Postgres-backed run queue in the Python service | Durable without Redis |
| D9 | Auth | Built-in NestJS JWT (`@nestjs/jwt` + `passport-jwt`), argon2 password hashing, rotating refresh tokens | Free, no vendor; swap to Better Auth/SuperTokens later if needed (see §7.1) |
| D10 | v1 autonomy | Human approval before every submission | Quality control, limits damage |
| D11 | v1 apply channels | Email + public ATS forms (Greenhouse, Lever, Workable) | No portal credentials stored; ToS-safe |
| D12 | File storage | S3-compatible (Cloudflare R2 / DO Spaces) | CVs, rendered PDFs |
| D13 | LLM observability | Langfuse (self-hosted) | Traces, cost per job, evals |
| D14 | Hosting v1 | Docker Compose on one VPS (DigitalOcean) | Cheap; split later |
| D15 | Tenancy | `tenant_id` on every row and request from day one | Retrofitting tenancy is expensive |
| D16 | Billing | Deferred (Stripe in SaaS phase) | Adding billing later is cheap |

---

## 2. System overview

```
┌──────────────┐  REST + SSE   ┌──────────────────┐   HTTP (internal)   ┌───────────────────────────┐
│ React / Vite │ ────────────▶ │   NestJS API     │ ──────────────────▶ │  Python agent service     │
│     SPA      │ ◀──────────── │  (public edge)   │ ◀────────────────── │  FastAPI + run worker     │
└──────────────┘               └────────┬─────────┘  signed callbacks   └─────────────┬─────────────┘
  Bearer access JWT                     │                                             │
  + httpOnly refresh cookie             ▼                                             ▼
                                ┌───────────────┐                          ┌─────────────────────┐
                                │ Postgres      │                          │ Postgres            │
                                │ schema: app   │                          │ schema: agents      │
                                └───────────────┘                          │ (runs, checkpoints, │
                                                                           │  outbox, artifacts) │
                                                                           └─────────────────────┘
                                                      External: LLM providers · R2/S3 · job sources · SMTP · ATS forms · Langfuse
```

Rules:
- The SPA talks **only** to Nest.
- The Python service has **no public ingress**. Only Nest calls it, over the private network.
- Each service owns its schema. Neither writes to the other's tables. Same Postgres server is fine for v1.

---

## 3. Services

### 3.1 Web (`apps/web`)
- React 19 + Vite, TanStack Router (file routes), TanStack Query for server state.
- API client generated from Nest's OpenAPI spec (`orval` or `openapi-typescript`).
- Live job progress via SSE from Nest. Native `EventSource` can't send an `Authorization` header, so use a fetch-based SSE client (`@microsoft/fetch-event-source`) with the Bearer access token.
- Auth client: access token held in memory; on `401`, call `/auth/refresh` once (cookie-based) and retry; on page load, call `/auth/refresh` to restore the session.
- Core screens: Onboarding (upload CV → structured profile), Preferences, Opportunities feed, Review queue (approve/edit/reject), Applications tracker, Settings.

### 3.2 Product API (`apps/api`, NestJS)

| Module | Responsibility |
|---|---|
| `auth` | Register/login/refresh/logout, global `JwtAuthGuard`, `@Public()` opt-out, resolves `user` + `tenant` into request context (see §7.1) |
| `tenants`, `users` | Accounts, membership |
| `profile` | Master profile (structured CV JSON), preferences, uploads |
| `opportunities` | Jobs surfaced to the user, match scores, dismiss/save |
| `runs` | Start agent runs, status, cancel, SSE stream |
| `applications` | Review queue, approval, submission status, history |
| `agent-client` | Typed HTTP client to the Python service; retries + idempotency |
| `internal-events` | `/internal/*` callback endpoints from Python; HMAC verification; ordered apply |
| `limits` | Per-tenant quotas (runs/day, applications/month, token budget), enforced before calling Python |
| `files` | Signed upload/download URLs for R2/S3 |
| `sweeper` | Cron: detect stuck runs, reconcile with Python |
| `billing` | *SaaS phase* — Stripe checkout, webhooks (raw body), plan enforcement |

Nest's `runs` table is the **source of truth** for run status shown to users.

### 3.3 Agent service (`services/agents`, Python)

Two processes from one codebase:

1. **`agents-api`** (FastAPI) — internal HTTP surface. Validates, inserts into `agents.run_queue`, returns `202`. Never executes graphs.
2. **`agents-worker`** — claims queued runs with `SELECT … FOR UPDATE SKIP LOCKED`, executes LangGraph graphs, writes events to the outbox, delivers them to Nest.

Worker properties:
- Bounded concurrency (global N + per-tenant cap).
- Bounded Playwright browser pool, separate from LLM concurrency.
- Heartbeat column on claimed runs; a stale heartbeat makes the run reclaimable.
- On start-up, resumes unfinished runs from the LangGraph Postgres checkpointer.
- Per-node retries (not per-run), per-run token budget.

---

## 4. Agent design (LangGraph)

v1 is a **fixed pipeline with one interrupt**, not a free-form supervisor. Easier to debug, cheaper, deterministic. A supervisor can be introduced once node boundaries are stable.

```
discover ──▶ normalize+dedupe ──▶ match/score ──▶ tailor CV ──▶ validate facts ──▶ render PDF
                                                                                       │
                                                       ┌───────────────────────────────┘
                                                       ▼
                                             ⏸ interrupt: human approval
                                                       │ approve / edit / reject
                                                       ▼
                                                 apply (email | ATS form)
                                                       │
                                                       ▼
                                                    track
```

| Node | Description | Model tier |
|---|---|---|
| `discover` | Pull offers from enabled source connectors using user preferences | — |
| `normalize_dedupe` | Common job schema; dedupe on (company, title, location) then embedding similarity | Embeddings |
| `match` | Score offer vs profile (embedding pre-filter → LLM rerank with rationale) | Cheap |
| `tailor` | Select, reorder, and rephrase **only** facts from the master profile; produce cover letter | Strong |
| `validate` | Every claim in the output must map to a profile fact; failures loop back to `tailor` (max 2) or flag for review | Cheap + rules |
| `render` | Structured CV → PDF (HTML template → Playwright PDF, or Typst) → R2 | — |
| `approval` | `interrupt()` — run pauses; Nest shows it in the review queue | — |
| `apply` | Email via SMTP, or fill public ATS form with Playwright. Unsupported targets → "ready-to-submit package" | — |
| `track` | Record submission, schedule follow-up checks | — |

### Graph state (sketch)
```python
class RunState(TypedDict):
    run_id: str
    tenant_id: str
    user_id: str
    profile: Profile                 # master profile snapshot (versioned)
    preferences: Preferences
    offers: list[JobOffer]
    scored: list[ScoredOffer]
    drafts: dict[str, ApplicationDraft]   # offer_id -> tailored CV + letter
    validation: dict[str, ValidationReport]
    decisions: dict[str, Decision]        # filled after interrupt resume
    usage: TokenUsage
```

### Anti-hallucination contract
- The master profile is a list of atomic, ID'd facts (role, dates, achievements, skills).
- `tailor` outputs content with `source_fact_ids` per bullet.
- `validate` rejects bullets with no source, changed numbers/dates, or invented skills.
- Validation report is shown in the review UI.

---

## 5. Contracts (Nest ↔ Python)

Defined as Pydantic models in Python → exported OpenAPI → TS types generated into `packages/contracts`. Never hand-maintained twice. All payloads carry `version`.

### 5.1 Nest → Python

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/runs` | Start run. Body: `{version, run_id, tenant_id, user_id, type, input, idempotency_key}` → `202 {run_id, status}` |
| `POST` | `/v1/runs/{run_id}/resume` | Resume after approval. Body: `{decisions: {offer_id: approve|edit|reject, edits?}}` |
| `POST` | `/v1/runs/{run_id}/cancel` | Cancel |
| `GET` | `/v1/runs/{run_id}` | Status + last checkpoint (used by sweeper) |
| `GET` | `/health` | Liveness/readiness |

- `run_id` is generated by Nest.
- Duplicate `idempotency_key` returns the existing run (safe retries).

### 5.2 Python → Nest (callbacks)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/internal/runs/{run_id}/events` | Batch of events |

Event:
```json
{
  "version": 1,
  "run_id": "…",
  "seq": 42,
  "type": "step_started | step_completed | offer_scored | draft_ready | awaiting_approval | application_submitted | usage | failed | completed",
  "step": "tailor",
  "data": {},
  "ts": "2026-11-08T12:00:00Z"
}
```

Delivery guarantees:
- **Transactional outbox** in Python: event row is written in the same transaction as the state change; a dispatcher delivers with exponential backoff until `2xx`.
- Nest dedupes on `(run_id, seq)` and applies in order; gaps are held until filled or reconciled by the sweeper.
- Requests signed with `X-Joby-Signature: HMAC-SHA256(secret, timestamp + body)` + `X-Joby-Timestamp` (reject > 5 min skew).
- `traceparent` header propagated both directions.

### 5.3 Timeouts
- Nest → Python calls: 5 s timeout, 3 retries with jitter (idempotent by design).
- Sweeper (every minute): runs in `running` with no event for > 10 min → `GET /v1/runs/{id}` → reconcile or mark `failed`.

---

## 6. Data model

### 6.1 `app` schema (Nest / Prisma) — core tables
| Table | Key columns |
|---|---|
| `tenants` | id, name, plan, created_at |
| `users` | id, tenant_id, email (unique), password_hash, role, email_verified_at, token_version |
| `refresh_tokens` | id, user_id, family_id, token_hash, expires_at, revoked_at, replaced_by, user_agent, ip |
| `profiles` | id, tenant_id, user_id, version, facts JSONB, raw_cv_file_id |
| `preferences` | tenant_id, user_id, roles[], locations[], remote, salary_min, languages[], sources[] |
| `opportunities` | id, tenant_id, source, external_id, url, company, title, location, description, posted_at, embedding vector, dedupe_hash |
| `matches` | tenant_id, user_id, opportunity_id, score, rationale, status (new/saved/dismissed) |
| `runs` | id, tenant_id, user_id, type, status, last_seq, started_at, finished_at, error |
| `run_events` | run_id, seq, type, step, data JSONB, ts — PK (run_id, seq) |
| `applications` | id, tenant_id, user_id, opportunity_id, run_id, cv_file_id, letter, validation JSONB, status (draft/awaiting_approval/approved/submitted/failed/rejected), channel, submitted_at |
| `files` | id, tenant_id, key, mime, size, kind |
| `usage` | tenant_id, run_id, model, input_tokens, output_tokens, cost_usd, ts |

### 6.2 `agents` schema (Python / Alembic)
| Table | Purpose |
|---|---|
| `run_queue` | run_id, tenant_id, payload, status, attempts, claimed_by, heartbeat_at, idempotency_key (unique) |
| `outbox` | id, run_id, seq, payload, delivered_at, attempts, next_attempt_at |
| LangGraph checkpointer tables | Graph state for resume/interrupt |
| `artifacts` | Intermediate outputs (raw scraped pages, prompts) with TTL |

### 6.3 Run status machine
```
queued → running → awaiting_approval → running → completed
            │                │
            └──▶ failed ◀────┘        (any) ──▶ cancelled
```

---

## 7. Security & privacy

### 7.1 Authentication (NestJS JWT)

| Item | Setup |
|---|---|
| Libraries | `@nestjs/jwt`, `@nestjs/passport`, `passport-jwt`, `argon2` |
| Password hashing | argon2id |
| Access token | JWT, 15 min, signed HS256 (`JWT_ACCESS_SECRET`). Claims: `sub` (user_id), `tid` (tenant_id), `role`, `tv` (token_version). Sent as `Authorization: Bearer`. Stored in memory in the SPA, never localStorage. |
| Refresh token | Opaque random 256-bit value, 30 days, `httpOnly; Secure; SameSite=Lax` cookie scoped to `/auth/refresh`. Stored hashed (SHA-256) in `refresh_tokens`. |
| Rotation | Every `/auth/refresh` issues a new pair and revokes the old token. Reuse of a revoked token → revoke the whole `family_id` (theft detection). |
| Logout | Revoke current refresh token. "Log out everywhere" → increment `users.token_version`; guard rejects access tokens with an older `tv`. |
| Guards | Global `JwtAuthGuard`; `@Public()` decorator for open routes; `RolesGuard` + `@Roles()`; tenant context injected from `tid`. |
| Endpoints | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/me` |
| Hardening | `@nestjs/throttler` on `/auth/*` (e.g. 5 login attempts/min per IP+email), generic error messages, constant-time compare, CORS restricted to the web origin with credentials |
| Deferred | Email verification, password reset, Google/LinkedIn OAuth, 2FA. Add them, or migrate to Better Auth/SuperTokens, when the SaaS phase starts. |
| Python service | Never sees user JWTs. Trusts Nest only via HMAC-signed internal calls (§5.2). |

### 7.2 Data protection

- CVs are personal data. Encrypt at rest (managed disk/bucket encryption), private buckets, short-lived signed URLs.
- Every query filtered by `tenant_id`. Prisma middleware/extension enforces it in Nest; repository layer enforces it in Python. Consider Postgres RLS in the SaaS phase.
- No job-portal credentials stored in v1.
- Secrets in env/secret manager, never in the repo. Separate HMAC secret per environment.
- Data rights: export and delete-account endpoints from day one. Compliance targets: Morocco Law 09-08 (CNDP) and GDPR for EU users.
- Rate-limit public endpoints in Nest (`@nestjs/throttler`).
- Respect each job source's terms of service; prefer official APIs/feeds. Connectors can be disabled per source.

---

## 8. Observability & quality

- **Tracing:** OpenTelemetry in Nest and Python; `traceparent` across HTTP calls and callbacks.
- **LLM traces:** Langfuse — per-node prompts, outputs, latency, tokens, cost; tagged with `tenant_id`, `run_id`.
- **Logs:** structured JSON, correlated by `trace_id` and `run_id`.
- **Metrics:** queue depth, run duration per node, failure rate per node, outbox lag, cost per run/tenant.
- **Evals:** fixed dataset of (profile, job) pairs with expected match ranking and validation results. Runs in CI on prompt/model changes; regressions block merge.

---

## 9. Repository layout

```
joby/
├── apps/
│   ├── web/                 # React + Vite
│   └── api/                 # NestJS
├── services/
│   └── agents/              # Python (uv): agents_api/, worker/, graphs/, connectors/, tools/, evals/
├── packages/
│   └── contracts/           # OpenAPI specs + generated TS types
├── infra/
│   ├── docker-compose.yml   # postgres, api, agents-api, agents-worker, web, langfuse
│   └── deploy/
├── docs/
│   └── ARCHITECTURE.md
├── pnpm-workspace.yaml
└── .github/workflows/
```

Tooling: pnpm workspace (TS), `uv` (Python), ESLint/Prettier, Ruff/mypy, Vitest/Jest, pytest, Playwright tests for E2E.

---

## 10. Environments & deployment

| Env | Setup |
|---|---|
| local | `docker compose up` — all services + Postgres + Langfuse |
| staging | Same Compose stack on a small VPS, separate DB and secrets |
| prod (v1) | Single VPS, Compose, Caddy reverse proxy (TLS), managed Postgres if budget allows, daily backups |

CI: lint → typecheck → unit tests → contract check (generated types up to date) → evals (on prompt/graph changes) → build images → deploy.

Scale path (SaaS phase): managed Postgres → move `agents-worker` to its own autoscaled nodes (scale on `run_queue` depth) → separate browser pool service → reconsider a broker (NATS/RabbitMQ) or gRPC only if HTTP + Postgres queue becomes the bottleneck.

---

## 11. Roadmap

| Phase | Scope |
|---|---|
| **M0 – Skeleton** | Monorepo, Compose, JWT auth (register/login/refresh), tenants/users, contracts pipeline, health checks, tracing |
| **M1 – Profile** | CV upload → parsed into atomic facts; edit profile & preferences |
| **M2 – Discover & match** | 1–2 source connectors, dedupe, embedding + LLM scoring, opportunities feed |
| **M3 – Tailor** | Tailor + validate + render PDF; review queue with interrupt/resume; SSE progress |
| **M4 – Apply** | Email channel, then one ATS form (Greenhouse or Lever); tracking |
| **M5 – Harden** | Outbox, sweeper, quotas, cost tracking, evals in CI, backups |
| **M6 – SaaS** | Stripe billing + plans, onboarding, RLS, landing page, admin dashboard |

---

## 12. Open questions

- Which job sources first (official APIs vs feeds vs user-pasted URLs)? Verify ToS per source.
- PDF rendering: HTML/Playwright vs Typst.
- Default LLM providers per tier and fallback policy.
- When (if ever) to allow approval-free auto-apply, and under which per-user rules.
- SaaS buyer: individual job seekers vs career services/schools.
