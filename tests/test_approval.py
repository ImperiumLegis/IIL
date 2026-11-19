import io
import json
from pathlib import Path

import pytest

from imperium_iil import approval


EXAMPLES = Path(__file__).resolve().parents[1] / "examples/exact-update"
A = EXAMPLES / "guide-a.json"
B = EXAMPLES / "guide-b.json"


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize(("candidate", "reply", "status"), [
    (A, "APPROVE\n", "APPROVAL_MATCHED"),
    (B, "APPROVE\n", "FRESH_REVIEW_REQUIRED"),
    (A, "no\n", "APPROVAL_DECLINED"),
    (A, "", "APPROVAL_DECLINED"),
])
def test_operator_comparison(candidate, reply, status):
    output = Terminal()
    assert approval.compare_in_session(A, candidate, Terminal(reply), output) == status
    assert "Run step 1" in output.getvalue()
    assert "Run step 2" not in output.getvalue()


def test_rechecks_after_confirmation(tmp_path):
    proposal = tmp_path / "proposal.json"
    proposal.write_bytes(A.read_bytes())

    class ChangedDuringReview(Terminal):
        def readline(self, limit):
            proposal.write_bytes(B.read_bytes())
            return super().readline(limit)

    assert approval.compare_in_session(proposal, proposal, ChangedDuringReview("APPROVE\n"),
                                       Terminal()) == "FRESH_REVIEW_REQUIRED"


def test_blocked_inputs(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    output = Terminal()
    assert approval.compare_in_session(invalid, A, Terminal("APPROVE\n"), output) == "REVIEW_BLOCKED"
    assert output.getvalue() == ""
    assert approval.compare_in_session(A, invalid, Terminal("APPROVE\n"), output) == "SUBMISSION_BLOCKED"


def test_cli_rejects_piped_approval(monkeypatch, capsys):
    monkeypatch.setattr(approval.sys, "stdin", io.StringIO("APPROVE\n"))
    assert approval.main([str(A), str(A)]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "REVIEW_TERMINAL_REQUIRED", "authority_granted": False}


def test_trusted_context_changes_during_review(tmp_path, monkeypatch):
    for name in ("demo-before-text.json", "exact-update-context.json"):
        (tmp_path / name).write_bytes((approval.FIXTURES / name).read_bytes())
    monkeypatch.setattr(approval, "FIXTURES", tmp_path)

    class ChangedContext(Terminal):
        def readline(self, limit):
            with (tmp_path / "exact-update-context.json").open("ab") as stream:
                stream.write(b" ")
            return super().readline(limit)

    assert approval.compare_in_session(A, A, ChangedContext("APPROVE\n"),
                                       Terminal()) == "FRESH_REVIEW_REQUIRED"
