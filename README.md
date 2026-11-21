# Joby

An AI agent that finds job opportunities, tailors a CV for each offer, and applies on the user's
behalf once they approve.

- Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Plan: [docs/ROADMAP.md](docs/ROADMAP.md)

## Layout

```
apps/web            React + Vite SPA (TanStack Router/Query, Tailwind, shadcn/ui)
apps/api            NestJS product API, Prisma, Postgres schema `app`
services/agents     Python: FastAPI agents-api + LangGraph worker, Alembic, schema `agents`
packages/contracts  OpenAPI specs + generated TypeScript types
infra               Docker Compose stack, Postgres init, deploy notes
```

## Run everything with Docker

```sh
cp infra/.env.example infra/.env   # then set real secrets
docker compose -f infra/docker-compose.yml up --build
```

| Service    | URL                                       |
| ---------- | ----------------------------------------- |
| web        | http://localhost:8080                     |
| api        | http://localhost:3000 (health: `/health`) |
| Langfuse   | http://localhost:3001                     |
| agents-api | internal only, not published              |

## Local development

Prerequisites: Node 22, pnpm (`corepack enable`), [uv](https://docs.astral.sh/uv/), and Postgres 16
with pgvector. The Compose `postgres` service works:
`docker compose -f infra/docker-compose.yml up -d postgres`.

```sh
pnpm install
cp apps/api/.env.example apps/api/.env
cp services/agents/.env.example services/agents/.env

# Migrations (each service owns its schema)
pnpm --filter @joby/api prisma:deploy
(cd services/agents && uv sync && uv run alembic upgrade head)

# Run
pnpm dev:api                                    # http://localhost:3000, docs at /docs
pnpm dev:web                                    # http://localhost:5173, proxies /api to the api
(cd services/agents && uv run uvicorn joby_agents.agents_api.app:app --reload --port 8000)
(cd services/agents && uv run joby-agents-worker)
```

## Checks

```sh
pnpm lint && pnpm typecheck && pnpm test        # TS packages
pnpm --filter @joby/api test:e2e                # needs DATABASE_URL
pnpm contracts:generate                         # after changing Pydantic models or Nest controllers
(cd services/agents && uv run ruff check . && uv run mypy src tests && uv run pytest)
```

## Contracts

Python Pydantic models and Nest controllers are the source of truth. `pnpm contracts:generate`
exports both OpenAPI specs to `packages/contracts/openapi/` and regenerates the TypeScript types.
CI fails if the committed output is stale.
