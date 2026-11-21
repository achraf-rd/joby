from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from joby_agents.agents_api.runs import router as runs_router
from joby_agents.contracts import HealthResponse, RunEventBatch
from joby_agents.db.session import get_session

app = FastAPI(
    title="Joby agents API",
    version="0.1.0",
    description="Internal surface. Only the NestJS API may call it; requests are HMAC-signed.",
)
app.include_router(runs_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="up")
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database="down")


@app.webhooks.post("run-events")
def run_events(body: RunEventBatch) -> None:
    """Callback delivered by this service to Nest at `POST /internal/runs/{run_id}/events`.

    Signed with X-Joby-Signature / X-Joby-Timestamp. Nest dedupes on (run_id, seq)
    and applies events in order (ARCHITECTURE §5.2).
    """
