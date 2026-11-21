"""LangGraph Postgres checkpointer, stored in the `agents` schema."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from joby_agents.settings import get_settings


@asynccontextmanager
async def checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    conn = await AsyncConnection.connect(
        get_settings().psycopg_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options="-c search_path=agents",
    )
    async with conn:
        yield AsyncPostgresSaver(conn)


async def setup_checkpointer() -> None:
    """Create or migrate the checkpointer tables. Idempotent."""
    async with checkpointer() as saver:
        await saver.setup()
