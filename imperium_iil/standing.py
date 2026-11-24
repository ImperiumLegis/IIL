"""Evaluate an actual call against an independently selected standing permission."""

import argparse
import json
from pathlib import Path

from .action_call import FORMATS, decode_call
from .action_manifest import document, load_catalog, read
from .action_policy import evaluate_document
from .reviewer_trust import require


def assess(policy, catalog, organization, requester, reviewer, permission, raw_call, call_format):
    """The host supplies identities and the permission from authenticated configuration."""
    tool, values = decode_call(raw_call, call_format)
    policy_doc = document(policy, numbers=True)
    rule = policy_doc["permissions"][permission]
    proposal = {"action":rule["action"], "version":rule["version"],
                "permission":permission, "arguments":values}
    action, _, _ = evaluate_document(policy_doc, proposal, catalog, organization, requester, reviewer)
    require(tool == action.tool)
    return {"status":"POLICY_MATCHED", "authority_granted":False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "registry", "policy", "call"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("organization", "requester", "reviewer", "permission"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--call-format", choices=FORMATS, default="iil")
    args = parser.parse_args(argv)
    try:
        result = assess(read(args.policy), load_catalog(args.registry, args.root), args.organization,
                        args.requester, args.reviewer, args.permission, read(args.call), args.call_format)
    except (ValueError, OSError, LookupError, TypeError):
        result = {"status":"POLICY_REJECTED", "authority_granted":False}
    print(json.dumps(result))
    return 0 if result["status"] == "POLICY_MATCHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
