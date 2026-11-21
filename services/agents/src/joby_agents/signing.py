"""HMAC request signing shared by both directions of Nest <-> Python traffic.

X-Joby-Signature = hex(HMAC-SHA256(secret, timestamp + body))
X-Joby-Timestamp = unix seconds; requests older/newer than the max skew are rejected.
"""

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-Joby-Signature"
TIMESTAMP_HEADER = "X-Joby-Timestamp"


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).hexdigest()


def signed_headers(secret: str, body: bytes, now: float | None = None) -> dict[str, str]:
    ts = str(int(now if now is not None else time.time()))
    return {SIGNATURE_HEADER: sign(secret, ts, body), TIMESTAMP_HEADER: ts}


def verify(
    secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    max_skew_seconds: int,
    now: float | None = None,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    current = now if now is not None else time.time()
    if abs(current - ts) > max_skew_seconds:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), signature)
