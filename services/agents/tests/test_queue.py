import uuid
from datetime import timedelta

from sqlalchemy import update

from joby_agents.db.models import QueueStatus, RunQueue
from joby_agents.db.session import get_sessionmaker
from joby_agents.worker import queue

STALE = timedelta(minutes=2)


async def enqueue(tenant_id: uuid.UUID) -> uuid.UUID:
    run_id = uuid.uuid4()
    async with get_sessionmaker()() as session:
        session.add(
            RunQueue(
                run_id=run_id,
                tenant_id=tenant_id,
                user_id=uuid.uuid4(),
                type="discover_and_apply",
                payload={},
                idempotency_key=str(run_id),
            )
        )
        await session.commit()
    return run_id


async def claim(worker: str = "w1", cap: int = 2) -> RunQueue | None:
    async with get_sessionmaker()() as session:
        return await queue.claim_next(session, worker, STALE, cap)


async def test_claims_oldest_and_marks_running() -> None:
    tenant = uuid.uuid4()
    first = await enqueue(tenant)
    await enqueue(tenant)

    run = await claim()
    assert run is not None
    assert run.run_id == first
    assert run.status == QueueStatus.running
    assert run.claimed_by == "w1"
    assert run.attempts == 1


async def test_respects_per_tenant_cap() -> None:
    busy, other = uuid.uuid4(), uuid.uuid4()
    await enqueue(busy)
    await enqueue(busy)
    other_run = await enqueue(other)

    first = await claim(cap=1)
    assert first is not None and first.tenant_id == busy
    second = await claim(cap=1)
    assert second is not None and second.run_id == other_run
    assert await claim(cap=1) is None


async def test_reclaims_stale_runs() -> None:
    run_id = await enqueue(uuid.uuid4())
    assert await claim("w1") is not None

    async with get_sessionmaker()() as session:
        await session.execute(
            update(RunQueue)
            .where(RunQueue.run_id == run_id)
            .values(heartbeat_at=RunQueue.heartbeat_at - timedelta(minutes=10))
        )
        await session.commit()

    reclaimed = await claim("w2")
    assert reclaimed is not None
    assert reclaimed.run_id == run_id
    assert reclaimed.claimed_by == "w2"
    assert reclaimed.attempts == 2


async def test_finish_ignores_cancelled_runs() -> None:
    run_id = await enqueue(uuid.uuid4())
    assert await claim("w1") is not None
    async with get_sessionmaker()() as session:
        await session.execute(
            update(RunQueue).where(RunQueue.run_id == run_id).values(status=QueueStatus.cancelled)
        )
        await session.commit()
        await queue.finish(session, run_id, "w1", QueueStatus.completed)
        run = await session.get(RunQueue, run_id, populate_existing=True)
    assert run is not None and run.status == QueueStatus.cancelled
