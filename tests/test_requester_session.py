import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil.requester_session import load_sessions


def entry(sid):
    public = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    return {"requester": "agent", "session": sid, "public_key": base64.b64encode(public).decode()}


def enrollment(*entries):
    return json.dumps({"version": "1", "organization": "demo", "sessions": entries}).encode()


def test_parallel_and_restarted_sessions():
    a, b = entry("a" * 64), entry("b" * 64)
    assert len(load_sessions(enrollment(a, b), "demo")) == 2
    assert a["session"] not in load_sessions(enrollment(b), "demo")
    replaced = entry(a["session"])
    assert load_sessions(enrollment(a), "demo") != load_sessions(enrollment(replaced), "demo")


@pytest.mark.parametrize("fault", ["duplicate_key", "duplicate_id", "bad_org", "extra", "point"])
def test_invalid_bindings(fault):
    a, b = entry("a" * 64), entry("b" * 64)
    if fault == "duplicate_key":
        b["public_key"] = a["public_key"]
    elif fault == "duplicate_id":
        b["session"] = a["session"]
    elif fault == "extra":
        b["scope"] = "*"
    elif fault == "point":
        b["public_key"] = base64.b64encode(bytes(32)).decode()
    with pytest.raises(ValueError):
        load_sessions(enrollment(a, b), "other" if fault == "bad_org" else "demo")
