# Build context: services/agents. One image, two processes (agents-api, agents-worker).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "joby_agents.agents_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
