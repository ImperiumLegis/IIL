"""Version one signed exact-review statements."""

from base64 import b64encode
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .parser import parse_bytes
from .reviewer_trust import binary, fields, matches, require

RECEIPT_LIMIT = 8192
WINDOW = timedelta(minutes=15)
SIGNED = ("format_version", "organization", "reviewer", "key_fingerprint",
          "review_fingerprint", "issued_at", "expires_at")


def timestamp(when):
    return when.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value):
    require(matches(value, r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"))
    return datetime.fromisoformat(value)


def check_time(claims, now):
    start = parse_time(claims["issued_at"])
    end = parse_time(claims["expires_at"])
    require(end - start == WINDOW and start <= now < end)


def make_claims(trust, reviewer, fingerprint, now):
    return {"format_version": "1", "organization": trust.organization, "reviewer": reviewer,
            "key_fingerprint": trust.lookup(reviewer).fingerprint, "review_fingerprint": fingerprint,
            "issued_at": timestamp(now), "expires_at": timestamp(now + WINDOW)}


def message(claims):
    chunks = [b"IIL-SIGNED-REVIEW\0"]
    for field in SIGNED:
        data = claims[field].encode("utf-8")
        chunks.extend((len(data).to_bytes(8, "big"), data))
    return b"".join(chunks)


def sign(claims, key):
    signature = b64encode(key.sign(message(claims))).decode("ascii")
    return {**claims, "signature": signature}


def authenticate(raw, trust, now):
    record = parse_bytes(raw, limit=RECEIPT_LIMIT)
    fields(record, (*SIGNED, "signature"))
    require(record["format_version"] == "1" and record["organization"] == trust.organization)
    reviewer = trust.lookup(record["reviewer"])
    require(record["key_fingerprint"] == reviewer.fingerprint)
    require(matches(record["review_fingerprint"], r"[a-f0-9]{64}"))
    check_time(record, now)
    key = Ed25519PublicKey.from_public_bytes(reviewer.public_key)
    try:
        key.verify(binary(record["signature"], 64), message(record))
    except InvalidSignature:
        raise ValueError("Invalid signature") from None
    return record
