import uuid

import httpx

from tests.conftest import SignedClient


def start_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "version": 1,
        "run_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "type": "discover_and_apply",
        "input": {},
        "idempotency_key": str(uuid.uuid4()),
    }
    body.update(overrides)
    return body


async def test_health(http: httpx.AsyncClient) -> None:
    res = await http.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "up"}


async def test_unsigned_request_is_rejected(http: httpx.AsyncClient) -> None:
    res = await http.post("/v1/runs", json=start_body())
    assert res.status_code == 401


async def test_start_run_is_idempotent(signed: SignedClient) -> None:
    body = start_body()
    first = await signed.request("POST", "/v1/runs", body)
    assert first.status_code == 202
    assert first.json() == {"run_id": body["run_id"], "status": "queued"}

    retry = await signed.request("POST", "/v1/runs", {**body, "run_id": str(uuid.uuid4())})
    assert retry.status_code == 202
    assert retry.json()["run_id"] == body["run_id"]


async def test_get_and_cancel_run(signed: SignedClient) -> None:
    body = start_body()
    await signed.request("POST", "/v1/runs", body)

    res = await signed.request("GET", f"/v1/runs/{body['run_id']}")
    assert res.status_code == 200
    assert res.json()["status"] == "queued"
    assert res.json()["last_seq"] == 0

    res = await signed.request("POST", f"/v1/runs/{body['run_id']}/cancel")
    assert res.json()["status"] == "cancelled"

    res = await signed.request("GET", f"/v1/runs/{body['run_id']}")
    assert res.json()["status"] == "cancelled"


async def test_unknown_run_is_404(signed: SignedClient) -> None:
    res = await signed.request("GET", f"/v1/runs/{uuid.uuid4()}")
    assert res.status_code == 404
