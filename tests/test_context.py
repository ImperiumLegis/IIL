import json
from copy import deepcopy
from pathlib import Path

import pytest

from imperium_iil.context import ContextError, TrustedContext, load_context, load_demo_context


@pytest.fixture
def bundle():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "demo-context.json"
    return json.loads(path.read_bytes())


def load(bundle):
    return load_context(json.dumps(bundle).encode())


def test_dangling_policy_group(bundle):
    bundle["denials"][0]["selector"]["value"] = "absent"
    with pytest.raises(ContextError):
        load(bundle)


def test_demo_snapshot_is_immutable():
    context = load_demo_context()
    snapshot = context.snapshots["repo-demo", "main"]
    assert snapshot["files"]["README.md"] == "regular"
    assert "docs/guide.md" in snapshot["eligible"]["github.file.update"]
    assert "docs/obsolete.md" in snapshot["eligible"]["github.file.delete"]
    assert "docs/guide.md" not in snapshot["eligible"]["github.file.delete"]
    with pytest.raises(TypeError):
        snapshot["files"]["README.md"] = "alias"
    with pytest.raises(TypeError):
        TrustedContext()


@pytest.mark.parametrize("complete, status", [(False, "reviewed"), (True, "claimed"), (True, "reviewed")])
def test_explicit_group_review(bundle, complete, status):
    group = bundle["snapshots"][0]["groups"]["authentication"]
    group.update(members=[], complete=complete)
    bundle["evidence"][group["review_ref"]]["status"] = status
    context = load(bundle)
    result = context.snapshots["repo-demo", "main"]["groups"]["authentication"]
    assert result["complete"] is complete
    assert context.evidence[result["review_ref"]] == status


@pytest.mark.parametrize("fault", [
    "duplicate_snapshot", "provider_alias", "missing_repo", "unknown_member", "unknown_review",
    "unknown_eligible", "unsupported_eligible", "nonregular_eligible", "invalid_path",
    "unknown_rule_capability", "unknown_rule_repo", "bad_selector", "bad_basename",
    "bad_selector_path", "unknown_field", "unsupported_promoted", "new_capability_promoted",
])
def test_invalid_bundle_is_operational_error(bundle, fault):
    snapshot = bundle["snapshots"][0]
    group = snapshot["groups"]["authentication"]
    denial = bundle["denials"][0]
    if fault == "duplicate_snapshot":
        bundle["snapshots"].append(deepcopy(snapshot))
    elif fault == "provider_alias":
        bundle["repositories"]["second"] = bundle["repositories"]["repo-demo"]
    elif fault == "missing_repo":
        snapshot["repository_id"] = "absent"
    elif fault == "unknown_member":
        group["members"].append("absent")
    elif fault == "unknown_review":
        group["review_ref"] = "absent"
    elif fault == "unknown_eligible":
        snapshot["eligible"]["github.file.read"].append("absent")
    elif fault == "unsupported_eligible":
        snapshot["eligible"]["github.pull_request.create"] = ["README.md"]
    elif fault == "nonregular_eligible":
        snapshot["eligible"]["github.file.read"].append("guide-link")
    elif fault == "invalid_path":
        snapshot["files"]["CON.txt"] = "regular"
    elif fault == "unknown_rule_capability":
        denial["capabilities"] = ["unknown.capability"]
    elif fault == "unknown_rule_repo":
        denial["repository_id"] = "absent"
    elif fault == "bad_selector":
        denial["selector"]["kind"] = "glob"
    elif fault == "bad_basename":
        denial["selector"] = {"kind": "basename", "value": "src/auth.py"}
    elif fault == "bad_selector_path":
        denial["selector"] = {"kind": "directory", "value": ".."}
    elif fault == "unknown_field":
        denial["approved"] = True
    elif fault == "unsupported_promoted":
        bundle["capabilities"]["github.pull_request.create"]["supported"] = True
    elif fault == "new_capability_promoted":
        bundle["capabilities"]["github.file.execute"] = bundle["capabilities"]["github.file.read"]
    with pytest.raises(ContextError):
        load(bundle)


@pytest.mark.parametrize("raw", [b'{"x":true,"x":false}', b'{}', b' ' * 1048577])
def test_reject_malformed_context(raw):
    with pytest.raises(ContextError):
        load_context(raw)


def test_context_array_boundary(bundle):
    rule = bundle["denials"][0]
    bundle["denials"] = [rule] * 1024
    assert len(load(bundle).denials) == 1024
    bundle["denials"].append(rule)
    with pytest.raises(ContextError):
        load(bundle)


def test_context_byte_boundary(bundle):
    raw = json.dumps(bundle).encode().ljust(1048576, b" ")
    assert load_context(raw).evidence["auth-review"] == "reviewed"
    with pytest.raises(ContextError):
        load_context(raw + b" ")


def test_context_source_text_boundary(bundle):
    record = bundle["evidence"]["auth-review"]
    record["source"] = "x" * 256
    assert load(bundle).evidence["auth-review"] == "reviewed"
    record["source"] += "x"
    with pytest.raises(ContextError):
        load(bundle)
