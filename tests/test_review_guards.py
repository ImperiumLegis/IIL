"""Exercise individual review guards without a second guard masking the result."""

import json

import pytest

from imperium_iil.action_manifest import arguments, document
from imperium_iil.action_policy import evaluate
from test_action_v2 import install_v2, encode


def test_manifest_range_without_policy(tmp_path):
    cat, _, doc = install_v2(tmp_path)
    action = cat["support.assign", "1"]
    values = doc["arguments"]
    for n in (0, 80):
        values["tickets"][0]["hours"] = n
        arguments(action, values)
    for n in (-1, 81):
        values["tickets"][0]["hours"] = n
        with pytest.raises(ValueError):
            arguments(action, values)


def test_boolean_constraint_on_valid_boolean(tmp_path):
    cat, policy, doc = install_v2(tmp_path)
    policy["permissions"]["assign"]["constraints"]["/tickets/*/notify"] = {"equals": False}
    def check():
        return evaluate(encode(policy), encode(doc), cat, "demo", "agent", "demo-reviewer")
    check()
    doc["arguments"]["tickets"][0]["notify"] = True
    with pytest.raises(ValueError):
        check()


def test_parser_magnitude_without_manifest():
    assert document(b'{"n":9007199254740991}', numbers=True)["n"] == 2**53 - 1
    for n in (2**53, -(2**53)):
        with pytest.raises(ValueError, match="NUMBER_LIMIT"):
            document(json.dumps({"n":n}).encode(), numbers=True)


def test_precision_loss_inside_magnitude_and_scale_limits():
    assert document(b'{"n":1000000000000.5}', numbers=True)["n"] == 1000000000000.5
    with pytest.raises(ValueError, match="NUMBER_PRECISION"):
        document(b'{"n":1000000000000.000001}', numbers=True)
