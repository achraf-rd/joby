"""agents-worker: claims runs from agents.run_queue and executes their graphs."""

import asyncio
import logging
import os
import signal
import socket
from datetime import timedelta

from joby_agents.db.models import QueueStatus, RunQueue
from joby_agents.db.session import get_sessionmaker
from joby_agents.graphs import REGISTRY
from joby_agents.graphs.checkpointer import setup_checkpointer
from joby_agents.settings import get_settings
from joby_agents.worker import queue

log = logging.getLogger("joby.worker")


class Worker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.sessions = get_sessionmaker()
        self.slots = asyncio.Semaphore(self.settings.worker_concurrency)
        self.stopping = asyncio.Event()
        self.tasks: set[asyncio.Task[None]] = set()

    async def run_forever(self) -> None:
        log.info(
            "worker %s started (concurrency=%d)", self.worker_id, self.settings.worker_concurrency
        )
        while not self.stopping.is_set():
            await self.slots.acquire()
            run = await self._claim()
            if run is None:
                self.slots.release()
                await self._sleep(self.settings.worker_poll_interval_seconds)
                continue
            task = asyncio.create_task(self._execute(run))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        await asyncio.gather(*self.tasks, return_exceptions=True)
        log.info("worker %s stopped", self.worker_id)

    async def _claim(self) -> RunQueue | None:
        async with self.sessions() as session:
            return await queue.claim_next(
                session,
                self.worker_id,
                timedelta(seconds=self.settings.worker_stale_after_seconds),
                self.settings.worker_per_tenant_concurrency,
            )

    async def _execute(self, run: RunQueue) -> None:
        beat = asyncio.create_task(self._heartbeat(run))
        try:
            runner = REGISTRY.get(run.type)
            if runner is None:
                await self._finish(
                    run, QueueStatus.failed, f"no graph registered for run type {run.type!r}"
                )
                return
            await runner(run)
            await self._finish(run, QueueStatus.completed)
        except Exception as exc:
            log.exception("run %s failed", run.run_id)
            await self._finish(run, QueueStatus.failed, str(exc))
        finally:
            beat.cancel()
            self.slots.release()

    async def _finish(self, run: RunQueue, status: QueueStatus, error: str | None = None) -> None:
        async with self.sessions() as session:
            await queue.finish(session, run.run_id, self.worker_id, status, error)

    async def _heartbeat(self, run: RunQueue) -> None:
        while True:
            await asyncio.sleep(self.settings.worker_heartbeat_interval_seconds)
            async with self.sessions() as session:
                await queue.heartbeat(session, run.run_id, self.worker_id)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stopping.wait(), timeout=seconds)
        except TimeoutError:
            pass


async def amain() -> None:
    await setup_checkpointer()
    worker = Worker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stopping.set)
    await worker.run_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(amain())


if __name__ == "__main__":
    main()
