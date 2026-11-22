import json
from argparse import Namespace
from pathlib import Path
import shutil
import sys

import pytest

from imperium_iil import action_receipt as ar
from imperium_iil.receipt import publish
from imperium_iil.requester_session import Session
from imperium_iil.session_proof import Presentation, respond
from test_receipt_cli import Terminal
from test_reviewer_trust import trust_for
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def operator(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1] / "examples/actions/email"
    shutil.copytree(root, tmp_path, dirs_exist_ok=True)
    key = Ed25519PrivateKey.generate()
    trust = trust_for(key)
    trust["reviewers"][0].update(id="demo-reviewer", grants=[])
    paths = Namespace(root=tmp_path, registry=tmp_path/"registry.json", trust=tmp_path/"trust.json",
                      key=None, policy=tmp_path/"policy.json", reviewer="demo-reviewer")
    paths.trust.write_text(json.dumps(trust))
    sk = Ed25519PrivateKey.generate()
    session = Session("demo","agent","a"*64,sk.public_key().public_bytes_raw())
    monkeypatch.setattr(ar,"unlock",lambda path:key)
    monkeypatch.setattr(sys,"stdin",Terminal("APPROVE\n"))
    output = Terminal()
    monkeypatch.setattr(sys,"stderr",output)
    return paths, session, sk, (tmp_path/"proposal.json").read_bytes(), (tmp_path/"call.json").read_bytes(), output


@pytest.mark.parametrize("stage", ["unlock", "confirm"])
def test_inactive_session_cannot_issue(operator, stage):
    paths, session, _, proposal, _, output = operator
    sequence = iter([session, session] if stage == "confirm" else [])
    with pytest.raises(StopIteration):
        ar.issue(paths, proposal, lambda:next(sequence))
    if stage == "unlock":
        assert output.getvalue() == ""


@pytest.mark.parametrize("case", ["ok", "mutable", "manifest", "policy", "grant", "session", "version"])
def test_receipt_and_final_recheck(operator, case):
    paths, session, key, proposal, call, _ = operator
    raw = ar.issue(paths, proposal, lambda:session)
    saved = paths.root/"out.json"
    publish(saved,json.loads(raw))
    assert saved.read_bytes() == raw
    pending = Presentation.for_submission(session,raw,call)
    if case == "mutable":
        call = bytearray(call)
    if case == "version":
        raw = raw.replace(b'action-1', b'2')
    active = [session]
    class Peer:
        def settimeout(self, timeout):
            pass
        def sendall(self, challenge):
            self.response = respond(key,pending,challenge)
        def recv(self, size):
            if case == "manifest":
                with (paths.root/"reply.json").open("ab") as stream:
                    stream.write(b" ")
            if case == "policy":
                with paths.policy.open("ab") as stream:
                    stream.write(b" ")
            if case == "grant":
                doc = json.loads(paths.policy.read_bytes())
                doc["permissions"]["support-reply"]["requesters"] = []
                paths.policy.write_text(json.dumps(doc))
            if case == "session":
                active[0] = Session("demo","agent","b"*64,session.public_key)
            return self.response
    result = ar.match(paths,proposal,raw,call,lambda:active[0],Peer())
    assert result["status"] == ("SESSION_CALL_MATCHED" if case == "ok" else "SESSION_CALL_REJECTED")
    assert result["authority_granted"] is False


def test_action_signature_framing_vector():
    claims = dict(zip(ar.NAMES, "abcdefghijklmn", strict=True))
    assert ar.message(claims) == b"IIL-DECLARATIVE-REVIEW-1\0" + b"".join(
        b"\0" * 7 + b"\x01" + bytes([c]) for c in b"abcdefghijklmn")
