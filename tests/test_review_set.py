import json
from pathlib import Path

from imperium_iil.review_set import review_set

ROOT = Path(__file__).resolve().parents[1]


def test_review_set_all_members_or_none():
    doc = json.loads((ROOT/"examples/exact-update/guide-a.json").read_bytes())
    context = json.loads((ROOT/"fixtures/exact-update-context.json").read_bytes())
    baseline = json.loads((ROOT/"fixtures/demo-before-text.json").read_bytes())
    op = doc["operations"][0]
    doc["iil_version"] = "set-1"
    doc["operations"].append({**op, "id":"op2","resource":{**op["resource"],"path":"README.md"}})
    context["snapshots"][0]["eligible"]["github.file.update"].append("README.md")
    baseline["entries"].append({**baseline["entries"][0], "path":"README.md"})
    def run():
        return review_set(*(json.dumps(x).encode() for x in (doc, context, baseline)))
    result = run()
    assert len(result["review"]["edits"]) == 2 and not result["authority_granted"]
    doc["operations"].reverse()
    assert result["review"]["fingerprint"] != run()["review"]["fingerprint"]
    doc["operations"][0]["resource"]["path"] = "src/auth.py"
    denied = run()
    assert denied["status"] == "INVALID" and "review" not in denied

def test_review_set_rejects_mutable_and_malformed_operator_data():
    import pytest
    raw = (ROOT/"fixtures/exact-update-context.json").read_bytes()
    before = (ROOT/"fixtures/demo-before-text.json").read_bytes()
    with pytest.raises(TypeError):
        review_set(bytearray(b"{}"), raw, before)
    with pytest.raises(ValueError):
        review_set(b"{}", raw, b"broken")

def test_set_member_keeps_only_its_repository_restrictions():
    doc = json.loads((ROOT/"examples/exact-update/guide-a.json").read_bytes())
    context = json.loads((ROOT/"fixtures/exact-update-context.json").read_bytes())
    baseline = json.loads((ROOT/"fixtures/demo-before-text.json").read_bytes())
    doc["iil_version"] = "set-1"
    context["repositories"]["repo-two"] = {"host":"github.example", "provider_id":"1002"}
    context["snapshots"].append({**context["snapshots"][0], "repository_id":"repo-two", "groups":{}})
    op = doc["operations"][0]
    doc["operations"].append({**op, "id":"op2", "resource":{**op["resource"], "repository_id":"repo-two"}})
    baseline["entries"].append({**baseline["entries"][0], "repository_id":"repo-two"})
    result = review_set(*(json.dumps(x).encode() for x in (doc, context, baseline)))
    assert result["status"] == "READY_FOR_REVIEW" and len(result["review"]["edits"]) == 2

def test_missing_second_baseline_suppresses_first_review():
    doc = json.loads((ROOT/"examples/exact-update/guide-a.json").read_bytes())
    context = json.loads((ROOT/"fixtures/exact-update-context.json").read_bytes())
    baseline = (ROOT/"fixtures/demo-before-text.json").read_bytes()
    doc["iil_version"] = "set-1"
    op = doc["operations"][0]
    doc["operations"].append({**op, "id":"op2", "resource":{**op["resource"],"path":"README.md"}})
    context["snapshots"][0]["eligible"]["github.file.update"].append("README.md")
    result = review_set(json.dumps(doc).encode(), json.dumps(context).encode(), baseline)
    assert result["status"] == "NEEDS_CLARIFICATION" and "review" not in result
    assert [(f["code"], f["pointer"]) for f in result["findings"]] == [
        ("MISSING_BASE_TEXT", "/operations/1/resource")]
