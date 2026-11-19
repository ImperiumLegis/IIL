import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("case", "status", "exit_code"), [
    ("valid/read_docs", "READY_FOR_REVIEW", 0),
    ("clarification/cleanup", "NEEDS_CLARIFICATION", 2),
    ("valid/update_docs", "READY_FOR_REVIEW", 0),
    ("unsupported/admin", "UNSUPPORTED", 3),
    ("invalid/protected", "INVALID", 4),
    ("invalid/forged_approval", "INVALID", 4),
    ("invalid/duplicate_key", "INVALID", 4),
    ("invalid/hidden_effect", "INVALID", 4),
    ("valid/prose_mismatch", "READY_FOR_REVIEW", 0),
    ("missing", "OPERATIONAL_ERROR", 1),
])
def test_cli(case, status, exit_code):
    run = subprocess.run(
        [sys.executable, "-m", "imperium_iil", "validate", f"examples/{case}.json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert run.returncode == exit_code, (run.stdout, run.stderr)
    payload = json.loads(run.stdout)
    assert payload["status"] == status and payload["authority_granted"] is False
    assert run.stderr == ""


def test_replay_and_library_results():
    from imperium_iil.context import load_demo_context
    from imperium_iil.validator import validate

    context = load_demo_context()
    raw = (ROOT / "examples/valid/read_docs.json").read_bytes()
    assert validate(raw, context).as_dict() == validate(raw, context).as_dict()
    proposal = json.loads(raw)
    proposal["context"]["catalog"]["version"] = "stale"
    proposal["evidence_refs"] = ["absent"]
    result = validate(json.dumps(proposal).encode(), context)
    assert result.status == "NEEDS_CLARIFICATION"
    assert "CONTEXT_MISMATCH" in {item.code for item in result.findings}


def test_unrelated_shape_error_preserves_known_scope_conflict():
    from imperium_iil.context import load_demo_context
    from imperium_iil.validator import validate

    doc = json.loads((ROOT / "examples/invalid/protected.json").read_bytes())
    doc["task"] = []
    result = validate(json.dumps(doc).encode(), load_demo_context())
    assert result.status == "INVALID"
    assert "POLICY_CONFLICT" in {f.code for f in result.findings}


def test_draft_claimed_evidence_cannot_satisfy_trusted_review():
    from imperium_iil.context import load_demo_context
    from imperium_iil.validator import validate

    doc = json.loads((ROOT / "examples/valid/read_docs.json").read_bytes())
    doc["evidence_refs"] = ["model-note"]
    result = validate(json.dumps(doc).encode(), load_demo_context())
    assert result.status == "NEEDS_CLARIFICATION"
    assert set(result.as_dict()["findings"][0]) == {"code", "pointer", "message"}


def test_bad_sibling_preserves_original_operation_pointer():
    from imperium_iil.context import load_demo_context
    from imperium_iil.validator import validate

    doc = json.loads((ROOT / "examples/invalid/protected.json").read_bytes())
    doc["operations"].insert(0, {})
    result = validate(json.dumps(doc).encode(), load_demo_context())
    assert ("POLICY_CONFLICT", "/operations/1") in {(f.code, f.pointer) for f in result.findings}


def test_missing_schema_is_operational_error(tmp_path):
    import shutil

    shutil.copytree(ROOT / "imperium_iil", tmp_path / "imperium_iil")
    run = subprocess.run([sys.executable, "-m", "imperium_iil", "validate", "proposal.json"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 1 and run.stderr == ""
    assert json.loads(run.stdout)["status"] == "OPERATIONAL_ERROR"
