import json
from argparse import Namespace
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil import session_match as sm
from imperium_iil.receipts import make_claims, sign
from imperium_iil.review import review_update
from imperium_iil.reviewer_trust import load_trust
from imperium_iil.requester_session import load_sessions
from imperium_iil.session_proof import Presentation, respond
from test_receipt_cli import ROOT, A
from test_requester_session import enrollment
from test_reviewer_trust import trust_for
from base64 import b64encode


@pytest.fixture
def comparison(tmp_path):
    key = Ed25519PrivateKey.generate()
    reviewer = Ed25519PrivateKey.generate()
    sid = "a" * 64
    entries = enrollment({"session": sid, "requester": "agent",
                          "public_key": b64encode(key.public_key().public_bytes_raw()).decode()})
    paths = Namespace(**{n: tmp_path / n for n in ("context", "baseline", "trust", "sessions")})
    paths.sessions.write_bytes(entries)
    binding = load_sessions(entries, "demo")[sid]
    paths.trust.write_text(json.dumps(trust_for(reviewer)))
    proposal = A.read_bytes()
    call = (ROOT / "examples/tool-calls/guide-a.json").read_bytes()
    paths.context.write_bytes((ROOT / "fixtures/exact-update-context.json").read_bytes())
    paths.baseline.write_bytes((ROOT / "fixtures/demo-before-text.json").read_bytes())
    fp = review_update(proposal, paths.context.read_bytes(), paths.baseline.read_bytes())["review"]["fingerprint"]
    at = sm.now().replace(microsecond=0)
    claims = make_claims(load_trust(paths.trust.read_bytes()), "alice", fp, at)
    claims.update(format_version="2", **binding.claims())
    receipt = json.dumps(sign(claims, reviewer)).encode()
    return paths, proposal, receipt, call, Presentation.for_submission(binding, receipt, call), key, at


@pytest.mark.parametrize("case", ["match", "wrong_key", "revoked", "removed", "context", "baseline",
                                  "rotated", "wall_expiry", "monotonic_expiry"])
def test_final_decision(comparison, case, monkeypatch):
    paths, proposal, receipt, call, pending, key, at = comparison
    ticks = [0.0]
    wall = [at]
    monkeypatch.setattr(sm, "now", lambda: wall[0])
    monkeypatch.setattr(sm, "monotonic", lambda: ticks[0])
    class Peer:
        def settimeout(self, timeout):
            assert 0 < timeout <= 60
        def sendall(self, challenge):
            self.challenge = challenge
    def read(peer, size, deadline):
        if case == "revoked":
            doc = json.loads(paths.trust.read_bytes())
            doc["reviewers"] = []
            paths.trust.write_text(json.dumps(doc))
        if case == "removed":
            paths.sessions.write_bytes(enrollment())
        if case == "rotated":
            doc = json.loads(paths.sessions.read_bytes())
            fresh = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
            doc["sessions"][0]["public_key"] = b64encode(fresh).decode()
            paths.sessions.write_text(json.dumps(doc))
        if case in ("context", "baseline"):
            with getattr(paths, case).open("ab") as stream:
                stream.write(b" ")
        if case == "wall_expiry":
            wall[0] += timedelta(minutes=15)
        if case == "monotonic_expiry":
            ticks[0] = 60
        if case == "wrong_key":
            return Ed25519PrivateKey.generate().sign(pending.message(peer.challenge[:32]))
        return respond(key, pending, peer.challenge)
    monkeypatch.setattr(sm, "receive", read)
    result = sm.check_session(paths, proposal, receipt, call, Peer())
    expected = "SESSION_CALL_MATCHED" if case == "match" else "SESSION_CALL_REJECTED"
    assert result == {"status": expected, "authority_granted": False}


def test_expiry_during_final_validation(comparison, monkeypatch):
    paths, proposal, receipt, call, pending, key, at = comparison
    clock = [at]
    monkeypatch.setattr(sm, "now", lambda: clock[0])
    class Peer:
        def settimeout(self, timeout):
            pass
        def sendall(self, challenge):
            self.challenge = challenge
    monkeypatch.setattr(sm, "receive", lambda peer, *_: respond(key, pending, peer.challenge))
    validate = sm._check_inputs
    checks = []
    def finish(*args):
        result = validate(*args)
        checks.append(result)
        if len(checks) == 2:
            clock[0] += timedelta(minutes=15)
        return result
    monkeypatch.setattr(sm, "_check_inputs", finish)
    assert sm.check_session(paths, proposal, receipt, call, Peer())["status"] == "SESSION_CALL_REJECTED"
    assert len(checks) == 2


def test_v1_receipt_cannot_start_challenge(comparison):
    paths, proposal, _, call, pending, _, at = comparison
    reviewer = Ed25519PrivateKey.generate()
    paths.trust.write_text(json.dumps(trust_for(reviewer)))
    artifact = review_update(proposal, paths.context.read_bytes(), paths.baseline.read_bytes())["review"]
    claims = make_claims(load_trust(paths.trust.read_bytes()), "alice", artifact["fingerprint"], at)
    raw = json.dumps(sign(claims, reviewer)).encode()
    class Peer:
        def settimeout(self, timeout):
            pytest.fail("v1 receipt reached proof exchange")
    assert sm.check_session(paths, proposal, raw, call, Peer())["status"] == "SESSION_CALL_REJECTED"


def test_crossed_simultaneous_responses(comparison, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    paths, proposal, receipt, call, pending, key, _ = comparison
    barrier = Barrier(2)
    challenges = {}
    class Peer:
        def __init__(self, index):
            self.index = index
        def settimeout(self, timeout):
            pass
        def sendall(self, challenge):
            challenges[self.index] = challenge
    def crossed(peer, size, deadline):
        barrier.wait(timeout=3)
        return respond(key, pending, challenges[1 - peer.index])
    monkeypatch.setattr(sm, "receive", crossed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(sm.check_session, paths, proposal, receipt, call, Peer(i)) for i in (0, 1)]
        assert all(job.result()["status"] == "SESSION_CALL_REJECTED" for job in jobs)
    assert challenges[0] != challenges[1]
