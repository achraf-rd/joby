# Roadmap: 7 steps to v1

Each step is one working session, delivered as **one branch and one pull request** for review
before the next step starts. Branch names: `agent/step-<n>-<slug>`.

The steps follow the milestones in [ARCHITECTURE.md §11](ARCHITECTURE.md#11-roadmap). M0 is split in two
(foundation, then auth), and deployment is folded into the hardening step so v1 ships at the end of step 7.

| Step | Milestone | Outcome                                                                             |
| ---- | --------- | ----------------------------------------------------------------------------------- |
| 1    | M0        | Monorepo runs locally and in Docker, both DB schemas exist, CI is green             |
| 2    | M0        | Users can register, log in and stay logged in; every request is tenant-scoped       |
| 3    | M1        | A user uploads a CV and gets an editable profile of atomic facts, plus preferences  |
| 4    | M2        | A run discovers offers from one source, scores them, and shows them in a live feed  |
| 5    | M3        | Tailored, fact-checked CV + letter per offer, paused for approval in a review queue |
| 6    | M4        | Approved applications are sent by email or a public ATS form and tracked            |
| 7    | M5        | Quotas, cost tracking, evals in CI, tracing, backups, deployed to a VPS             |

---

## Step 1: Foundation (M0, part 1)

**Scope**

- pnpm workspace (`apps/api`, `apps/web`, `packages/contracts`) + uv project (`services/agents`).
- NestJS API: env validation, Prisma with every `app` table from §6.1, `/health`, OpenAPI at `/docs`.
- Agent service: `agents` schema (run queue, outbox, artifacts) via Alembic, LangGraph checkpointer,
  HMAC-signed `/v1/runs` (start / get / cancel; resume returns 501), worker with `SKIP LOCKED` claim,
  per-tenant cap, heartbeat and stale-run reclaim.
- Contracts pipeline: Pydantic + Nest OpenAPI → TypeScript types in `packages/contracts`.
- Web shell: React + Vite, TanStack Router/Query, Tailwind, shadcn config, typed API client.
- Docker Compose (Postgres + pgvector, api, agents-api, agents-worker, web, Langfuse), CI.

**Done when** `docker compose up` brings every service up healthy, a signed run is claimed by the
worker, and CI passes.

## Step 2: Auth and tenancy (M0, part 2)

**Scope**

- `auth` module per §7.1: register (creates tenant + owner), login, refresh with rotation and
  family revocation, logout, logout-all (`token_version`), `GET /auth/me`.
- argon2id, 15-min HS256 access JWT, opaque refresh token in an httpOnly cookie, `@nestjs/throttler` on `/auth/*`.
- Global `JwtAuthGuard`, `@Public()`, `RolesGuard`, tenant context from `tid`.
- Prisma extension that enforces `tenant_id` on tenant-scoped models.
- Web: login/register pages, in-memory access token, refresh-on-401 and on page load, protected route layout.

**Done when** e2e tests cover the full token lifecycle, including reuse detection, and the web app keeps a session across reloads.

**Decide at start:** registration open or invite-only for the personal-use phase.

## Step 3: Profile and CV ingestion (M1)

**Scope**

- `files` module: S3-compatible signed upload/download (MinIO in Compose for local dev).
- CV upload → first real agent run: parse PDF/DOCX into atomic, ID'd facts (§4 contract).
- Nest ↔ Python plumbing used for the first time: `agent-client` (timeouts, retries, idempotency),
  `internal-events` (HMAC verify, dedupe on `(run_id, seq)`, ordered apply), outbox dispatcher in Python.
- Profile versioning; profile editor and preferences screen.

**Done when** uploading a real CV produces an editable fact list, and edits create a new profile version.

**Decide at start:** LLM provider and model for parsing (§12).

## Step 4: Discover and match (M2)

**Scope**

- `discover_and_apply` graph, first nodes: `discover`, `normalize_dedupe`, `match`.
- One or two source connectors (official APIs/feeds first, ToS checked per source).
- Embeddings into `opportunities.embedding`, then LLM rerank with rationale.
- `runs` module: start, cancel, status, SSE stream (fetch-based client in web).
- Opportunities feed: score, rationale, save/dismiss.

**Done when** a run started from the UI streams progress and fills the feed with scored, deduplicated offers.

**Decide at start:** which sources, embedding model (sets the `vector(...)` dimension).

## Step 5: Tailor, validate, review (M3)

**Scope**

- `tailor` (facts only, `source_fact_ids` per bullet, cover letter), `validate` (loop back max 2), `render` to PDF.
- `approval` interrupt; `POST /v1/runs/{id}/resume` implemented; checkpoint resume after worker restart.
- Review queue UI: diff vs. profile, validation report, approve / edit / reject.

**Done when** a run pauses with drafts in the review queue, and approve/edit/reject resumes it correctly, also after a worker restart.

**Decide at start:** PDF renderer (HTML + Playwright vs Typst).

## Step 6: Apply and track (M4)

**Scope**

- `apply` node: email channel via SMTP, then one ATS form (Greenhouse or Lever) with a bounded Playwright pool.
- Unsupported targets produce a ready-to-submit package.
- `track` node and the applications tracker screen.

**Done when** an approved application is actually sent (to a test inbox / sandbox posting) and its status is visible in the tracker.

## Step 7: Harden and ship v1 (M5)

**Scope**

- `limits` (runs/day, applications/month, token budget), `usage` cost tracking, `sweeper` cron.
- OpenTelemetry in both services with `traceparent` across calls, Langfuse traces per node.
- Eval dataset + CI job on prompt/graph changes.
- Data export and account deletion endpoints.
- Deploy: Compose on a VPS behind Caddy, separate staging, daily backups.

**Done when** v1 runs in production, and CI blocks regressions in lint, tests, contracts and evals.

---

## After v1: SaaS (M6)

Stripe billing and plans, onboarding, Postgres RLS, admin dashboard, and the public **landing page**.
Design reference for the landing page: [capy.ai](https://capy.ai/) (structure, mono-forward typography,
tight radii, all-caps section eyebrows). Borrow the layout and patterns, not Capy's brand: no mascot, no teal palette.
