import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from joby_agents.agents_api.security import require_signature
from joby_agents.contracts import (
    ResumeRunRequest,
    RunAccepted,
    RunStatus,
    RunStatusResponse,
    StartRunRequest,
)
from joby_agents.db.models import TERMINAL_STATUSES, Outbox, QueueStatus, RunQueue
from joby_agents.db.session import get_session

router = APIRouter(prefix="/v1/runs", tags=["runs"], dependencies=[Depends(require_signature)])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=RunAccepted)
async def start_run(body: StartRunRequest, session: Session) -> RunAccepted:
    """Enqueue a run. Never executes the graph here; the worker claims it.

    A duplicate idempotency_key returns the existing run, so Nest can retry safely.
    """
    stmt = (
        insert(RunQueue)
        .values(
            run_id=body.run_id,
            tenant_id=body.tenant_id,
            user_id=body.user_id,
            type=body.type.value,
            payload=body.model_dump(mode="json"),
            status=QueueStatus.queued,
            idempotency_key=body.idempotency_key,
        )
        .on_conflict_do_nothing(index_elements=[RunQueue.idempotency_key])
        .returning(RunQueue.run_id, RunQueue.status)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        existing = await session.scalar(
            select(RunQueue).where(RunQueue.idempotency_key == body.idempotency_key)
        )
        assert existing is not None
        return RunAccepted(run_id=existing.run_id, status=RunStatus(existing.status))
    await session.commit()
    return RunAccepted(run_id=row.run_id, status=RunStatus(row.status))


async def _get_or_404(session: AsyncSession, run_id: uuid.UUID) -> RunQueue:
    run = await session.get(RunQueue, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: uuid.UUID, session: Session) -> RunStatusResponse:
    """Status and progress, used by Nest's sweeper to reconcile stuck runs."""
    run = await _get_or_404(session, run_id)
    last_seq = await session.scalar(
        select(func.coalesce(func.max(Outbox.seq), 0)).where(Outbox.run_id == run_id)
    )
    return RunStatusResponse(
        run_id=run.run_id,
        status=RunStatus(run.status),
        attempts=run.attempts,
        heartbeat_at=run.heartbeat_at,
        error=run.error,
        last_seq=last_seq or 0,
    )


@router.post("/{run_id}/cancel", response_model=RunAccepted)
async def cancel_run(run_id: uuid.UUID, session: Session) -> RunAccepted:
    run = await _get_or_404(session, run_id)
    if run.status not in TERMINAL_STATUSES:
        await session.execute(
            update(RunQueue).where(RunQueue.run_id == run_id).values(status=QueueStatus.cancelled)
        )
        await session.commit()
        return RunAccepted(run_id=run_id, status=RunStatus.cancelled)
    return RunAccepted(run_id=run_id, status=RunStatus(run.status))


@router.post("/{run_id}/resume", response_model=RunAccepted)
async def resume_run(run_id: uuid.UUID, body: ResumeRunRequest, session: Session) -> RunAccepted:
    """Resume a run paused at the approval interrupt (milestone M3)."""
    await _get_or_404(session, run_id)
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED, "resume lands with the approval interrupt (M3)"
    )
