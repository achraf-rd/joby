"""Postgres-backed run queue operations (ARCHITECTURE §3.3, D8)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from joby_agents.db.models import QueueStatus, RunQueue


async def claim_next(
    session: AsyncSession,
    worker_id: str,
    stale_after: timedelta,
    per_tenant_cap: int,
) -> RunQueue | None:
    """Claim one queued (or stale running) run with FOR UPDATE SKIP LOCKED.

    Tenants already at their concurrency cap are skipped. Commits the claim.
    """
    stale_before = datetime.now(UTC) - stale_after
    running_per_tenant = (
        select(RunQueue.tenant_id)
        .where(
            RunQueue.status == QueueStatus.running,
            RunQueue.heartbeat_at >= stale_before,
        )
        .group_by(RunQueue.tenant_id)
        .having(func.count() >= per_tenant_cap)
    )
    candidate = (
        select(RunQueue)
        .where(
            or_(
                RunQueue.status == QueueStatus.queued,
                and_(
                    RunQueue.status == QueueStatus.running,
                    RunQueue.heartbeat_at < stale_before,
                ),
            ),
            RunQueue.tenant_id.not_in(running_per_tenant),
        )
        .order_by(RunQueue.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = await session.scalar(candidate)
    if run is None:
        await session.rollback()
        return None
    run.status = QueueStatus.running
    run.claimed_by = worker_id
    run.heartbeat_at = func.now()
    run.attempts += 1
    await session.commit()
    await session.refresh(run)
    return run


async def heartbeat(session: AsyncSession, run_id: uuid.UUID, worker_id: str) -> None:
    await session.execute(
        update(RunQueue)
        .where(RunQueue.run_id == run_id, RunQueue.claimed_by == worker_id)
        .values(heartbeat_at=func.now())
    )
    await session.commit()


async def finish(
    session: AsyncSession,
    run_id: uuid.UUID,
    worker_id: str,
    status: QueueStatus,
    error: str | None = None,
) -> None:
    """Set a final status unless the run was cancelled or reclaimed meanwhile."""
    await session.execute(
        update(RunQueue)
        .where(
            RunQueue.run_id == run_id,
            RunQueue.claimed_by == worker_id,
            RunQueue.status == QueueStatus.running,
        )
        .values(status=status, error=error)
    )
    await session.commit()
