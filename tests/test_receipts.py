from datetime import UTC, datetime, timedelta
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil.receipts import make_claims, message, sign, authenticate
from imperium_iil.reviewer_trust import load_trust
from test_reviewer_trust import trust_for

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def signed():
    key = Ed25519PrivateKey.generate()
    trust = load_trust(json.dumps(trust_for(key)).encode())
    claims = make_claims(trust, "alice", "a" * 64, NOW)
    return sign(claims, key), trust


def test_frame():
    names = ("format_version", "organization", "reviewer", "key_fingerprint",
             "review_fingerprint", "issued_at", "expires_at")
    vector = dict(zip(names, "1234567"))
    assert message(vector) == b"IIL-SIGNED-REVIEW\x00" + b"".join(
        b"\x00" * 7 + b"\x01" + bytes([n]) for n in range(49, 56))


@pytest.mark.parametrize("offset,valid", [(-1, False), (0, True), (899, True), (900, False)])
def test_time_window(signed, offset, valid):
    doc, trust = signed
    now = NOW + timedelta(seconds=offset)
    if valid:
        assert authenticate(json.dumps(doc).encode(), trust, now)["reviewer"] == "alice"
    else:
        with pytest.raises(ValueError):
            authenticate(json.dumps(doc).encode(), trust, now)


@pytest.mark.parametrize("field", ["format_version", "organization", "reviewer", "key_fingerprint",
                                   "review_fingerprint", "issued_at", "expires_at", "signature", "trust"])
def test_changed_receipt(signed, field):
    doc, trust = signed
    doc[field] = {"review_fingerprint": "b" * 64}.get(field, "x")
    with pytest.raises(ValueError):
        authenticate(json.dumps(doc).encode(), trust, NOW)


@pytest.mark.parametrize("raw", [b'{}', b'{"a":"a","a":"b"}', b' ' * 8193])
def test_bad_envelope(signed, raw):
    with pytest.raises(ValueError):
        authenticate(raw, signed[1], NOW)
