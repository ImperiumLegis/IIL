import json

import pytest

from imperium_iil.action_manifest import load_catalog
from imperium_iil.action_policy import evaluate
from test_action_manifest import install


@pytest.mark.parametrize("change", ["none", "mix", "outsider", "stale", "org", "unknown", "extra"])
def test_both_grants_and_every_member(tmp_path, change):
    path, pin = install(tmp_path)
    cat = load_catalog(path, tmp_path)
    rule = {**pin, "requesters": ["robot"], "reviewers": ["alice"], "constraints": {"lists": "allowed"}}
    groups = {"allowed": ["new", "warm"]}
    permissions = {"capture": rule}
    args = {"name": "lead", "lists": ["new", "warm"]}
    if change == "mix":
        permissions["other"] = {**rule, "requesters": []}
        rule["reviewers"] = []
    elif change == "outsider":
        args["lists"].insert(1, "private")
    elif change == "stale":
        rule["sha256"] = "0"*64
    elif change == "unknown":
        rule["constraints"]["missing"] = "allowed"
    elif change == "extra":
        args["hidden"] = "x"
    policy = json.dumps({"organization":"demo","groups":groups,"permissions":permissions}).encode()
    proposal = json.dumps({"action":pin["action"], "version":"1","permission":"capture","arguments":args}).encode()
    def review():
        return evaluate(policy, proposal, cat, "other" if change == "org" else "demo", "robot", "alice")
    if change == "none":
        assert review()[2] == args
    else:
        with pytest.raises(ValueError):
            review()
