"""Compare one complete synthetic tool call with a signed exact update offline."""

import argparse
import json
from pathlib import Path
import sys

from .__main__ import FIXTURES, FIXTURE_LIMIT, _read
from .receipt import now, verified_review
from .receipts import RECEIPT_LIMIT, check_time
from .reviewer_trust import TRUST_LIMIT, UPDATE, load_trust, require
from .tool_call import CALL_LIMIT, UpdateCall, parse_update_call
from .validator import PROPOSAL_LIMIT


def match(args):
    raw_call = _read(args.call, CALL_LIMIT)
    proposal = _read(args.proposal, PROPOSAL_LIMIT)
    receipt = _read(args.receipt, RECEIPT_LIMIT)
    context = _read(args.context, FIXTURE_LIMIT)
    baseline = _read(args.baseline, FIXTURE_LIMIT)
    trust = load_trust(_read(args.trust, TRUST_LIMIT))

    submitted = parse_update_call(raw_call)
    claims, artifact, repo = verified_review(proposal, receipt, context, baseline, trust, now())
    compare_call(submitted, artifact, repo)
    check_time(claims, now())


def compare_call(submitted, artifact, repo):
    target = artifact["target"]
    expected = UpdateCall(action=UPDATE, host=repo["host"], provider_id=repo["provider_id"],
                          branch=target["branch"], base_revision=target["revision"],
                          path=target["path"], text=artifact["after"].encode("utf-8"))
    require(submitted == expected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    for name in ("call", "receipt", "trust"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--context", type=Path, default=FIXTURES / "exact-update-context.json")
    parser.add_argument("--baseline", type=Path, default=FIXTURES / "demo-before-text.json")
    args = parser.parse_args(argv)
    try:
        match(args)
    except (Exception, KeyboardInterrupt):
        # Diagnostics at this boundary must not disclose submitted or protected text.
        print(json.dumps({"status": "TOOL_CALL_REJECTED", "authority_granted": False}))
        return 1
    print(json.dumps({"status": "TOOL_CALL_MATCHED", "authority_granted": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
