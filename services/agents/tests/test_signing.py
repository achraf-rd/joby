from joby_agents.signing import sign, signed_headers, verify

SECRET = "s3cret"
BODY = b'{"hello":"world"}'


def test_round_trip() -> None:
    headers = signed_headers(SECRET, BODY, now=1_000)
    assert verify(
        SECRET, headers["X-Joby-Timestamp"], headers["X-Joby-Signature"], BODY, 300, now=1_000
    )


def test_rejects_tampered_body() -> None:
    headers = signed_headers(SECRET, BODY, now=1_000)
    assert not verify(
        SECRET, headers["X-Joby-Timestamp"], headers["X-Joby-Signature"], b"{}", 300, now=1_000
    )


def test_rejects_wrong_secret() -> None:
    sig = sign("other", "1000", BODY)
    assert not verify(SECRET, "1000", sig, BODY, 300, now=1_000)


def test_rejects_clock_skew() -> None:
    headers = signed_headers(SECRET, BODY, now=1_000)
    assert not verify(
        SECRET, headers["X-Joby-Timestamp"], headers["X-Joby-Signature"], BODY, 300, now=1_301
    )


def test_rejects_missing_or_malformed_headers() -> None:
    assert not verify(SECRET, None, "x", BODY, 300)
    assert not verify(SECRET, "not-a-number", "x", BODY, 300)
