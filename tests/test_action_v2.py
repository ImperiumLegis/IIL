import hashlib
import json

import pytest

from imperium_iil.action_manifest import arguments, document, load_catalog
from imperium_iil.action_policy import evaluate


def encode(value):
    return json.dumps(value).encode()


def install_v2(root, change=None):
    tag = {"type": "string", "min": "1", "max": "24", "pattern": "team-*"}
    record = {"team": tag, "hours": {"type": "number", "min": 0, "max": 80},
              "priority": {"type": "enum", "values": ["low", "high"]},
              "notify": {"type": "boolean"}, "copies": {"type": "integer", "min": 1, "max": 3}}
    manifest = {"format_version": "2", "action": "support.assign", "version": "1",
                "tool": "assign_tickets", "fields": {"tickets": {"type": "array",
                "least": "1", "most": "4", "items": {"type": "object", "fields": record}}}}
    if change:
        change(manifest, record)
    raw = encode(manifest)
    (root / "assign.json").write_bytes(raw)
    pin = {"action": "support.assign", "version": "1", "sha256": hashlib.sha256(raw).hexdigest()}
    registry = root / "registry.json"
    registry.write_bytes(encode({"version": "1", "entries": [{**pin, "file": "assign.json"}]}))
    cat = load_catalog(registry, root)
    constraints = {"/tickets/*/hours": {"min": 0, "max": 8.5},
                   "/tickets/*/team": {"pattern": "team-e*"}, "/tickets/*/priority": "allowed"}
    policy = {"organization": "demo", "groups": {"allowed": ["low"]}, "permissions": {"assign":
              {**pin, "requesters": ["agent"], "reviewers": ["demo-reviewer"], "constraints": constraints}}}
    ticket = {"team": "team-east", "hours": 8.25, "priority": "low", "notify": False, "copies": 1}
    proposal = {"action": "support.assign", "version": "1", "permission": "assign",
                "arguments": {"tickets": [ticket]}}
    return cat, policy, proposal


def test_review_nested_ticket(tmp_path):
    cat, policy, proposal = install_v2(tmp_path)
    reviewed = evaluate(encode(policy), encode(proposal), cat, "demo", "agent", "demo-reviewer")
    assert reviewed[2] == proposal["arguments"]


@pytest.mark.parametrize("amend", [
    {"notify": 0}, {"copies": True}, {"copies": 1.0}, {"hours": True},
    {"hours": "8.25"}, {"hours": 8.500001}, {"hours": -1}, {"priority": "high"},
    {"priority": "urgent"}, {"team": "team-west"}, {"team": "team-e/other"},
    {"team": "team-e"}, {"unexpected": "value"},
])
def test_every_nested_item_must_meet_schema_and_permission(tmp_path, amend):
    cat, policy, doc = install_v2(tmp_path)
    tickets = doc["arguments"]["tickets"]
    tickets.append({**tickets[0], **amend})
    with pytest.raises(ValueError):
        evaluate(encode(policy), encode(doc), cat, "demo", "agent", "demo-reviewer")


@pytest.mark.parametrize("selector,rule", [
    ("/tickets/0/hours", {"min": 0, "max": 5}), ("/tickets/*/missing", "allowed"),
    ("/tickets/*/hours", {"min": 2, "max": 1}), ("/tickets/*/hours", {"pattern": "3*"}),
    ("/tickets/*/team", {"pattern": "*"}), ("/tickets/*/team", {"pattern": "*a*"}),
    ("/tickets/*/team", {"pattern": "[abc]*"}), ("/tickets/*/copies", {"min": False, "max": 3}),
])
def test_invalid_policy_rejected_even_if_permission_unselected(tmp_path, selector, rule):
    cat, policy, doc = install_v2(tmp_path)
    policy["permissions"]["unused"] = {**policy["permissions"]["assign"], "constraints": {selector: rule}}
    with pytest.raises(ValueError):
        evaluate(encode(policy), encode(doc), cat, "demo", "agent", "demo-reviewer")


@pytest.mark.parametrize("change", [
    lambda m, r: m.update(format_version="3"),
    lambda m, r: r["priority"].update(values=["low", "low"]),
    lambda m, r: r["team"].update(pattern="*"),
    lambda m, r: r["hours"].update(min=True),
    lambda m, r: r["copies"].update(max=2.5),
    lambda m, r: r["notify"].update(default=True),
])
def test_malformed_manifest(tmp_path, change):
    with pytest.raises(ValueError):
        install_v2(tmp_path, change)


def test_action_numbers_are_finite_bounded_and_unambiguous(tmp_path):
    cat, _, doc = install_v2(tmp_path)
    action = cat["support.assign", "1"]
    raw = encode(doc["arguments"])
    for token in (b"NaN", b"Infinity", b"1e9999", b"-0.0", b"9007199254740992", b"8.25000000000000001"):
        with pytest.raises(ValueError):
            arguments(action, document(raw.replace(b"8.25", token), numbers=True))
