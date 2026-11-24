import base64
import json
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil.reviewer_trust import load_trust


def trust_for(key):
    public = key.public_key().public_bytes_raw()
    return {"format_version": "1", "organization": "demo", "reviewers": [{
        "id": "alice", "public_key": base64.b64encode(public).decode(),
        "grants": [{"host": "github.example", "provider_id": "1001", "action": "github.file.update"}],
    }]}


def test_empty_and_scoped_trust():
    doc = trust_for(Ed25519PrivateKey.generate())
    trust = load_trust(json.dumps(doc).encode())
    assert trust.lookup("alice").allows({"host": "github.example", "provider_id": "1001"})
    assert not trust.lookup("alice").allows({"host": "github.example", "provider_id": "1002"})
    doc["reviewers"] = []
    with pytest.raises(ValueError):
        load_trust(json.dumps(doc).encode()).lookup("alice")


@pytest.mark.parametrize("change", ["repeat_key", "repeat_id", "bad_key", "wildcard", "extra", "bad_type"])
def test_malformed_trust(change):
    doc = trust_for(Ed25519PrivateKey.generate())
    entry = doc["reviewers"][0]
    if change == "repeat_key":
        doc["reviewers"].append({**entry, "id": "bob"})
    elif change == "repeat_id":
        doc["reviewers"].extend(trust_for(Ed25519PrivateKey.generate())["reviewers"])
    elif change == "bad_key":
        entry["public_key"] = "AAAA"
    elif change == "wildcard":
        entry["grants"][0]["host"] = "*"
    elif change == "extra":
        doc["approved"] = "yes"
    else:
        entry["grants"] = {}
    with pytest.raises(ValueError):
        load_trust(json.dumps(doc).encode())


def test_reject_invalid_public_point():
    doc = trust_for(Ed25519PrivateKey.generate())
    doc["reviewers"][0]["public_key"] = base64.b64encode(bytes(32)).decode()
    with pytest.raises(ValueError):
        load_trust(json.dumps(doc).encode())


def test_pin_requires_digest_of_immutable_snapshot():
    raw = json.dumps(trust_for(Ed25519PrivateKey.generate())).encode()
    pin = sha256(raw).hexdigest()
    assert load_trust(raw, expected_sha256=pin.upper()).organization == "demo"
    for snapshot, expected in [(raw + b" ", pin), (raw, ""), (raw, pin + "\n"),
                               (bytearray(raw), pin)]:
        with pytest.raises(ValueError):
            load_trust(snapshot, expected_sha256=expected)
