import json
from pathlib import Path
import subprocess
import sys


def test_separate_requester_processes():
    run = subprocess.run([sys.executable, "-m", "examples.session_demo"], capture_output=True,
                         cwd=Path(__file__).resolve().parents[1], text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    results = json.loads(run.stdout)
    assert list(results) == ["approved_session", "other_session", "recorded_proof", "restarted_session"]
    for name, result in results.items():
        expected = "SESSION_CALL_MATCHED" if name == "approved_session" else "SESSION_CALL_REJECTED"
        assert result == {"status": expected, "authority_granted": False}
    assert run.stderr == ""


def test_honest_requester_prepares_from_own_session(tmp_path):
    from types import SimpleNamespace
    from examples import session_demo as demo

    (tmp_path / "sessions.json").write_text('{"version":"1","organization":"demo","sessions":[]}')
    (tmp_path / "receipt.json").write_bytes(b"public receipt")
    class ClosedChannel:
        def sendall(self, data):
            assert len(data) == 32
        def settimeout(self, timeout):
            pass
        def recv(self, size):
            return b""
        def close(self):
            pass
    demo._requester([ClosedChannel()], SimpleNamespace(wait=lambda _: True), tmp_path, "a" * 64, False)
