from fastapi import HTTPException, Request, status

from joby_agents.settings import get_settings
from joby_agents.signing import SIGNATURE_HEADER, TIMESTAMP_HEADER, verify


async def require_signature(request: Request) -> None:
    """Only Nest may call this service: verify the HMAC over timestamp + raw body."""
    settings = get_settings()
    body = await request.body()
    ok = verify(
        settings.internal_hmac_secret,
        request.headers.get(TIMESTAMP_HEADER),
        request.headers.get(SIGNATURE_HEADER),
        body,
        settings.signature_max_skew_seconds,
    )
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")
