import json
from argparse import Namespace
from pathlib import Path
import shutil
import sys
from hashlib import sha256

import pytest

from imperium_iil import action_receipt as ar
from imperium_iil.receipt import publish
from imperium_iil.requester_session import Session
from imperium_iil.session_proof import Presentation, respond
from test_receipt_cli import Terminal
from test_reviewer_trust import trust_for
from test_action_v2 import encode, install_v2
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


@pytest.mark.parametrize("case", ["ok", "mutable", "manifest", "policy", "grant", "session", "version", "trust_pin"])
def test_receipt_and_final_recheck(operator, case):
    paths, session, key, proposal, call, _ = operator
    paths.trust_sha256 = sha256(paths.trust.read_bytes()).hexdigest()
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
            if case == "trust_pin":
                with paths.trust.open("ab") as stream:
                    stream.write(b" ")
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


@pytest.mark.parametrize("adapter,case", [
    ("iil", "ok"), ("mcp", "ok"), ("openai-chat", "ok"),
    ("mcp", "change-adapter"), ("mcp", "method"), ("mcp", "meta"), ("mcp", "bool-id"),
    ("openai-chat", "duplicates"), ("openai-chat", "extra"), ("openai-chat", "changed-hours"),
    ("iil", "numeric-type"), ("iil", "numeric-equivalent"),
])
def test_typed_adapter_receipt(operator, adapter, case, capsys):
    paths, session, key, _, _, _ = operator
    _, policy, proposal = install_v2(paths.root)
    paths.policy.write_bytes(encode(policy))
    args = proposal["arguments"]
    if case.startswith("numeric"):
        args["tickets"][0]["hours"] = 8.0
    reviewed = encode(proposal)
    paths.call_format = adapter
    receipt = ar.issue(paths, reviewed, lambda: session)
    assert '"notify": false' in capsys.readouterr().err
    if case == "change-adapter":
        paths.call_format = "iil"
    if case == "changed-hours":
        args["tickets"][0]["hours"] = 7.25
    if case == "numeric-type":
        args["tickets"][0]["hours"] = 8
    if paths.call_format == "mcp":
        envelope = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "assign_tickets", "arguments": args}}
        if case == "method":
            envelope["method"] = "tools/list"
        if case == "meta":
            envelope["params"]["_meta"] = {"extra": True}
        if case == "bool-id":
            envelope["id"] = True
    elif paths.call_format == "openai-chat":
        encoded = json.dumps(args)
        if case == "duplicates":
            encoded = encoded.replace('"copies": 1', '"copies": 3, "copies": 1')
        envelope = {"id": "call_1", "type": "function",
                    "function": {"name": "assign_tickets", "arguments": encoded}}
        if case == "extra":
            envelope["function"]["execute"] = True
    else:
        envelope = {"tool": "assign_tickets", "arguments": args}
    call = encode(envelope)
    if case == "numeric-equivalent":
        call = call.replace(b"8.0", b"8.00")
    pending = Presentation.for_submission(session, receipt, call)

    class Peer:
        def settimeout(self, timeout):
            pass
        def sendall(self, challenge):
            self.response = respond(key, pending, challenge)
        def recv(self, size):
            return self.response

    result = ar.match(paths, reviewed, receipt, call, lambda: session, Peer())
    matched = case in ("ok", "numeric-equivalent")
    assert result == {"status": "SESSION_CALL_MATCHED" if matched else "SESSION_CALL_REJECTED",
                      "authority_granted": False}


def test_signed_action_task_is_displayed_and_bound(operator, capsys):
    paths, session, _, proposal, call, _ = operator
    doc = json.loads(proposal)
    doc["task"] = {"description": "Reply about support ticket 42."}
    receipt = ar.issue(paths, encode(doc), lambda: session)
    preview = capsys.readouterr().err
    assert doc["task"]["description"] in preview and "subject" in preview
    digest = json.loads(receipt)["review_fingerprint"]
    doc["task"]["description"] = "Reply about support ticket 43."
    assert ar.review(paths, encode(doc), session)[-1] != digest
    assert ar.match(paths, encode(doc), receipt, call, lambda: session, None)["status"] == "SESSION_CALL_REJECTED"


@pytest.mark.parametrize("invalid", [None, "prose", {}, {"description": " "},
                                     {"description": "x" * 1025}, {"description": "ok", "override": True}])
def test_malformed_action_task_rejects_before_confirmation(operator, invalid, capsys):
    paths, session, _, proposal, _, _ = operator
    doc = json.loads(proposal)
    doc["task"] = invalid
    with pytest.raises(ValueError):
        ar.issue(paths, encode(doc), lambda: session)
    assert "APPROVE" not in capsys.readouterr().err
