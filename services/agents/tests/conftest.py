"""Integration tests run against DATABASE_URL with migrations applied (alembic upgrade head)."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import delete

from joby_agents.agents_api.app import app
from joby_agents.db.models import RunQueue
from joby_agents.db.session import get_sessionmaker
from joby_agents.settings import get_settings
from joby_agents.signing import signed_headers


class SignedClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def request(self, method: str, url: str, body: Any = None) -> httpx.Response:
        raw = b"" if body is None else json.dumps(body).encode()
        headers = signed_headers(get_settings().internal_hmac_secret, raw)
        headers["content-type"] = "application/json"
        return await self.client.request(method, url, content=raw, headers=headers)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def signed(http: httpx.AsyncClient) -> SignedClient:
    return SignedClient(http)


@pytest.fixture(autouse=True)
async def clean_queue() -> AsyncIterator[None]:
    yield
    async with get_sessionmaker()() as session:
        await session.execute(delete(RunQueue))
        await session.commit()
