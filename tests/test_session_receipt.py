import json

import pytest

from imperium_iil import receipt
from imperium_iil.receipts import SIGNED, authenticate, message
from test_receipt_cli import issue, setup
from test_requester_session import enrollment, entry


def test_session_receipt(setup, tmp_path, monkeypatch):
    args, trust, _, out = setup
    binding = entry("a" * 64)
    sessions = tmp_path / "sessions"
    sessions.write_bytes(enrollment(binding))
    args[0] = "issue-session"
    args.extend(["--sessions", str(sessions), "--session", binding["session"]])
    code, preview = issue(args, monkeypatch, "APPROVE\n")
    assert code == 0 and binding["session"] in preview and '"agent"' in preview
    trust = receipt.load_trust(trust.read_bytes())
    def verify(raw, version):
        return authenticate(raw, trust, receipt.now(), version=version)
    raw = out.read_bytes()
    assert verify(raw, "2")["requester"] == "agent"
    with pytest.raises(ValueError):
        verify(raw, "1")
    for name in ("requester", "session", "session_key_fingerprint"):
        record = json.loads(raw)
        record[name] = "b" * 64
        with pytest.raises(ValueError):
            verify(json.dumps(record).encode(), "2")


def test_v2_frame():
    names = (*SIGNED, "requester", "session", "session_key_fingerprint")
    claims = dict(zip(names, "23456789ab"))
    assert message(claims) == b"IIL-SESSION-REVIEW\0" + b"".join(
        b"\0" * 7 + b"\1" + bytes([v]) for v in b"23456789ab")


def test_session_removed_at_confirmation(setup, tmp_path, monkeypatch):
    import sys
    from test_receipt_cli import Terminal

    args, _, _, out = setup
    binding = entry("a" * 64)
    sessions = tmp_path / "sessions"
    sessions.write_bytes(enrollment(binding))
    args[0] = "issue-session"
    args.extend(["--sessions", str(sessions), "--session", binding["session"]])

    class Confirm(Terminal):
        def readline(self, limit):
            sessions.write_bytes(enrollment())
            return "APPROVE\n"

    monkeypatch.setattr(sys, "stdin", Confirm())
    monkeypatch.setattr(sys, "stderr", Terminal())
    monkeypatch.setattr(receipt.getpass, "getpass", lambda *args: "disposable")
    assert receipt.main(args) == 1
    assert not out.exists()
