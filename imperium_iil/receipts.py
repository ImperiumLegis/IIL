"""Version one signed exact-review statements."""

from base64 import b64encode
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .parser import parse_bytes
from .reviewer_trust import binary, fields, identifier, matches, require

RECEIPT_LIMIT = 8192
WINDOW = timedelta(minutes=15)
SIGNED = ("format_version", "organization", "reviewer", "key_fingerprint",
          "review_fingerprint", "issued_at", "expires_at")
SESSION_SIGNED = (*SIGNED, "requester", "session", "session_key_fingerprint")


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


def framed(domain, values):
    chunks = [domain + b"\0"]
    for data in values:
        chunks.extend((len(data).to_bytes(8, "big"), data))
    return b"".join(chunks)


def message(claims):
    version = claims["format_version"]
    require(version in ("1", "2"))
    domain, names = ((b"IIL-SIGNED-REVIEW", SIGNED) if version == "1"
                     else (b"IIL-SESSION-REVIEW", SESSION_SIGNED))
    return framed(domain, (claims[name].encode("utf-8") for name in names))


def sign(claims, key):
    signature = b64encode(key.sign(message(claims))).decode("ascii")
    return {**claims, "signature": signature}


def authenticate(raw, trust, now, *, version="1"):
    record = parse_bytes(raw, limit=RECEIPT_LIMIT)
    require(version in ("1", "2") and record.get("format_version") == version)
    fields(record, (*(SIGNED if version == "1" else SESSION_SIGNED), "signature"))
    require(record["organization"] == trust.organization)
    if version == "2":
        identifier(record["requester"])
        require(matches(record["session"], r"[a-f0-9]{64}"))
        require(matches(record["session_key_fingerprint"], r"[a-f0-9]{64}"))
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
