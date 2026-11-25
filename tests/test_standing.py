from pathlib import Path
import json
import pytest
from imperium_iil.standing import assess
from imperium_iil.action_manifest import load_catalog
from test_action_manifest import install
from test_action_v2 import encode, install_v2

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


def test_no_argument_mcp_call_checks_empty_manifest_and_progress_metadata(tmp_path):
    catalog, policy, _ = install_v2(tmp_path, lambda manifest, record: manifest.update(fields={}))
    policy["permissions"]["assign"]["constraints"] = {}
    inputs = (encode(policy), catalog, "demo", "agent", "demo-reviewer", "assign")
    params = {"name": "assign_tickets"}
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
    for meta in ({}, {"progressToken": 0}, {"progressToken": 2.5}, {"progressToken": "task-42"}):
        params["_meta"] = meta
        assert assess(*inputs, encode(call), "mcp")["status"] == "POLICY_MATCHED"
    for meta in (None, [], {"progressToken": True}, {"progressToken": {}}, {"unknown": "side effect"}):
        params["_meta"] = meta
        with pytest.raises(ValueError):
            assess(*inputs, encode(call), "mcp")
    del params["_meta"]
    params["arguments"] = {"extra": "value"}
    with pytest.raises(ValueError):
        assess(*inputs, encode(call), "mcp")


def test_mcp_omitted_arguments_still_reject_missing_required_fields(tmp_path):
    catalog, policy, _ = install_v2(tmp_path)
    args = (encode(policy), catalog, "demo", "agent", "demo-reviewer", "assign")
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "assign_tickets"}}
    with pytest.raises(ValueError):
        assess(*args, encode(call), "mcp")
