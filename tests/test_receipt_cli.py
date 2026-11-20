import io
import json
from pathlib import Path
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from imperium_iil import receipt
from test_reviewer_trust import trust_for

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "examples/exact-update/guide-a.json"
B = ROOT / "examples/exact-update/guide-b.json"


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def setup(tmp_path):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "signer.pem"
    private.write_bytes(key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8,
                                          ser.BestAvailableEncryption(b"disposable")))
    trust = tmp_path / "trust.json"
    trust.write_text(json.dumps(trust_for(key)))
    out = tmp_path / "receipt.json"
    args = ["issue", str(A), "--trust", str(trust), "--key", str(private), "--reviewer", "alice",
            "--out", str(out)]
    return args, trust, private, out


def issue(args, monkeypatch, reply, tty=True):
    terminal = Terminal()
    with monkeypatch.context() as m:
        m.setattr(sys, "stderr", terminal)
        m.setattr(sys, "stdin", Terminal(reply) if tty else io.StringIO(reply))
        m.setattr(receipt.getpass, "getpass", lambda *a, **kw: "disposable")
        code = receipt.main(args)
    return code, terminal.getvalue()


@pytest.mark.parametrize("case", ["declined", "eof", "redirect", "unenrolled", "wrong_key",
                                  "clear_key", "remap", "blocked", "revoked"])
def test_no_failed_receipt(setup, case, monkeypatch):
    args, trust, private, out = setup
    doc = json.loads(trust.read_bytes())
    reviewer = doc["reviewers"][0]
    reply = "APPROVE\n"
    if case == "declined":
        reply = "no\n"
    elif case == "eof":
        reply = ""
    elif case == "unenrolled":
        doc["reviewers"] = []
    elif case == "revoked":
        reviewer["grants"] = []
    elif case == "remap":
        ctx = json.loads((ROOT / "fixtures/exact-update-context.json").read_bytes())
        ctx["repositories"]["repo-demo"]["provider_id"] = "2002"
        path = out.with_name("remap.json")
        path.write_text(json.dumps(ctx))
        args.extend(["--context", str(path)])
    elif case == "wrong_key":
        reviewer["public_key"] = trust_for(Ed25519PrivateKey.generate())["reviewers"][0]["public_key"]
    elif case == "clear_key":
        private.write_bytes(Ed25519PrivateKey.generate().private_bytes(
            ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
    elif case == "blocked":
        ctx = json.loads((ROOT / "fixtures/exact-update-context.json").read_bytes())
        ctx["denials"].append({"repository_id": "repo-demo", "capabilities": ["github.file.read"],
                               "selector": {"kind": "exact_path", "value": "docs/guide.md"}})
        path = out.with_name("blocked.json")
        path.write_text(json.dumps(ctx))
        args.extend(["--context", str(path)])
    trust.write_text(json.dumps(doc))
    code, preview = issue(args, monkeypatch, reply, case != "redirect")
    assert code != 0 and not out.exists()
    if case not in {"declined", "eof"}:
        assert "Run step" not in preview and "Run the demo" not in preview


def test_transfer_and_revocation(setup, monkeypatch):
    args, trust, private, out = setup
    code, preview = issue(args, monkeypatch, "APPROVE\n")
    assert code == 0 and "Run step 1" in preview
    private.unlink()
    def verify(proposal, *extra):
        run = subprocess.run([sys.executable, "-m", "imperium_iil.receipt", "verify", str(proposal),
                              "--trust", str(trust), "--receipt", str(out), *map(str, extra)],
                             cwd=ROOT, capture_output=True, text=True, check=False)
        payload = json.loads(run.stdout)
        assert payload["authority_granted"] is False
        return run.returncode, payload["status"]
    assert verify(A) == (0, "APPROVAL_VERIFIED")
    assert verify(B)[0] != 0
    for option, fixture in [("--context", "exact-update-context.json"),
                            ("--baseline", "demo-before-text.json")]:
        changed = out.with_name(fixture)
        changed.write_bytes((ROOT / "fixtures" / fixture).read_bytes() + b" ")
        assert verify(A, option, changed)[0] != 0
    original = trust.read_bytes()
    for change in ("organization", "remove_grant", "remove_key"):
        doc = json.loads(original)
        if change == "organization":
            doc["organization"] = "other"
        elif change == "remove_grant":
            doc["reviewers"][0]["grants"] = []
        else:
            doc["reviewers"] = []
        trust.write_text(json.dumps(doc))
        assert verify(A)[0] != 0


@pytest.mark.parametrize("stage", ["unlock", "confirm"])
def test_revoked_while_waiting(setup, stage, monkeypatch):
    args, trust, private, out = setup
    def revoke():
        doc = json.loads(trust.read_bytes())
        doc["reviewers"] = []
        trust.write_text(json.dumps(doc))
    def passphrase(*a, **kw):
        if stage == "unlock":
            revoke()
        return "disposable"
    class Confirm(Terminal):
        def readline(self, limit):
            if stage == "confirm":
                revoke()
            return "APPROVE\n"
    terminal = Terminal()
    monkeypatch.setattr(sys, "stdin", Confirm())
    monkeypatch.setattr(sys, "stderr", terminal)
    monkeypatch.setattr(receipt.getpass, "getpass", passphrase)
    assert receipt.main(args) != 0
    assert not out.exists()
    if stage == "unlock":
        assert "Run step" not in terminal.getvalue()
