from pathlib import Path
import json
import pytest
from imperium_iil.standing import assess
from imperium_iil.action_manifest import load_catalog
from test_action_manifest import install

ROOT = Path(__file__).resolve().parents[1]/"examples/actions/email"


def test_standing_policy_checks_actual_call_without_signing():
    catalog = load_catalog(ROOT/"registry.json", ROOT)
    args = ((ROOT/"policy.json").read_bytes(), catalog, "demo", "agent", "demo-reviewer", "support-reply")
    wire = json.loads((ROOT/"call.json").read_bytes())
    def check():
        return assess(*args, json.dumps(wire).encode(), "iil")
    assert check() == {"status":"POLICY_MATCHED","authority_granted":False}
    wire["arguments"]["to"] = ["outside@example.test"]
    with pytest.raises(ValueError):
        check()
    wire["arguments"]["to"] = ["alice@example.test"]
    wire["tool"] = "other"
    with pytest.raises(ValueError):
        check()


def test_standing_validates_wire_size_without_inventing_a_larger_proposal(tmp_path):
    registry, pin = install(tmp_path)
    catalog = load_catalog(registry, tmp_path)
    rule = {**pin, "requesters": ["agent"], "reviewers": ["alice"], "constraints": {}}
    policy = json.dumps({"organization": "demo", "groups": {}, "permissions": {"capture": rule}}).encode()
    args = {"name": "", "lists": ["x" * 16000] * 4 + [""]}
    call = {"tool": "create_lead", "arguments": args}

    def encoded():
        return json.dumps(call, separators=(",", ":")).encode()

    args["lists"][-1] = "x" * (65536 - len(encoded()))
    wire = encoded()
    assert len(wire) == 65536
    inputs = (policy, catalog, "demo", "agent", "alice", "capture")
    assert assess(*inputs, wire, "iil") == {"status": "POLICY_MATCHED", "authority_granted": False}
    with pytest.raises(ValueError):
        assess(*inputs, wire + b" ", "iil")
