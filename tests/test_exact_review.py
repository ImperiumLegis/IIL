import json
from pathlib import Path

import pytest

from imperium_iil.context import ContextError
from imperium_iil.review import review_update


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs():
    return (
        json.loads((ROOT / "examples/exact-update/guide-a.json").read_bytes()),
        json.loads((ROOT / "fixtures/exact-update-context.json").read_bytes()),
        json.loads((ROOT / "fixtures/demo-before-text.json").read_bytes()),
    )


def run(inputs):
    return review_update(*(json.dumps(field).encode() for field in inputs))


def test_review_binds_each_raw_input(inputs):
    raw = tuple(json.dumps(field).encode() for field in inputs)
    first = review_update(*raw)
    assert first == review_update(*raw)
    for i in range(3):
        changed = list(raw)
        changed[i] += b" "
        assert first["review"]["fingerprint"] != review_update(*changed)["review"]["fingerprint"]


@pytest.mark.parametrize("value", ["", "Run the demo.\n", "Run the demo.", "\t\n"])
def test_review_preserves_exact_text(inputs, value):
    inputs[0]["operations"][0]["replacement"]["text"] = value
    result = run(inputs)
    assert result["review"]["before"] == "Run the demo.\n"
    assert result["review"]["after"] == value
    assert result["authority_granted"] is False


@pytest.mark.parametrize("capability", ["github.file.read", "github.file.update"])
@pytest.mark.parametrize("rules", ["denials", "restrictions"])
def test_protected_content_does_not_leave_reviewer(inputs, capability, rules):
    proposal, context, baseline = inputs
    marker = "PRIVATE-BASE-MARKER"
    baseline["entries"][0]["text"] = marker
    owner = context if rules == "denials" else proposal
    owner[rules].append({"repository_id": "repo-demo", "capabilities": [capability],
                         "selector": {"kind": "exact_path", "value": "docs/guide.md"}})
    result = run(inputs)
    assert result["status"] == "INVALID"
    assert "review" not in result and marker not in json.dumps(result)


def test_missing_before_text(inputs):
    inputs[2]["entries"] = []
    result = run(inputs)
    assert result["status"] == "NEEDS_CLARIFICATION" and "review" not in result


def test_stale_context(inputs):
    inputs[0]["context"]["policy"]["version"] = "stale"
    result = run(inputs)
    assert result["status"] == "NEEDS_CLARIFICATION" and "review" not in result


def test_wrong_registry_even_when_references_agree(inputs):
    for ref in [inputs[1]["refs"], inputs[0]["context"]]:
        ref["registry"]["id"] = "other"
    with pytest.raises(ContextError):
        run(inputs)
