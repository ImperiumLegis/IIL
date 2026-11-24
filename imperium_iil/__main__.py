"""Offline validator CLI. All proposed resource paths remain data."""

import argparse
import json
from pathlib import Path
import sys

from .resources import resource_dir

EXIT_CODES = {"READY_FOR_REVIEW": 0, "NEEDS_CLARIFICATION": 2, "UNSUPPORTED": 3, "INVALID": 4}
FIXTURES = resource_dir("fixtures")
FIXTURE_LIMIT = 1_048_576


def _read(path, limit):
    with path.open("rb") as stream:
        return stream.read(limit + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review an IIL proposal against operator-selected context.")
    parser.add_argument("command", choices=["validate", "review", "review-set"])
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--context", type=Path, help="trusted context JSON")
    parser.add_argument("--baseline", type=Path, help="trusted before-text JSON for review")
    parser.add_argument("--snapshot", type=Path, help="trusted context and baseline from iil-snapshot")
    args = parser.parse_args(argv)
    if args.snapshot and (args.context or args.baseline):
        parser.error("choose the snapshot or separate inputs")
    if args.command == "validate" and args.baseline:
        parser.error("--baseline requires review")
    if args.command != "validate" and bool(args.context) != bool(args.baseline):
        parser.error("supply both --context and --baseline for a custom review")
    try:
        from .context import load_context
        from .validator import PROPOSAL_LIMIT, validate

        from .review import EXACT_PROPOSAL_LIMIT, review_update
        from .review_set import review_set
        from .parser import parse_bytes

        exact = args.command != "validate"
        proposal = _read(args.proposal, EXACT_PROPOSAL_LIMIT if exact else PROPOSAL_LIMIT)
        if args.snapshot:
            limit = 2 * FIXTURE_LIMIT + 128
            snapshot = parse_bytes(_read(args.snapshot, limit), limit=limit)
            if set(snapshot) != {"context", "baseline"}:
                raise ValueError("Invalid snapshot bundle")
            context = json.dumps(snapshot["context"]).encode()
            baseline = json.dumps(snapshot["baseline"]).encode()
        else:
            demo = "exact-update-context.json" if exact else "demo-context.json"
            context = _read(args.context or FIXTURES / demo, FIXTURE_LIMIT)
            if exact:
                baseline = _read(args.baseline or FIXTURES / "demo-before-text.json", FIXTURE_LIMIT)
        if exact:
            review = review_update if args.command == "review" else review_set
            payload = review(proposal, context, baseline)
        else:
            payload = validate(proposal, load_context(context)).as_dict()
        code = EXIT_CODES[payload["status"]]
    except (OSError, ValueError):
        payload = {"status": "OPERATIONAL_ERROR", "authority_granted": False,
                   "code": "INPUT_OR_CONTEXT_UNAVAILABLE"}
        code = 1
    except Exception:
        # Public CLI boundary: an unexpected failure must not disclose proposal data.
        payload = {"status": "OPERATIONAL_ERROR", "authority_granted": False,
                   "code": "VALIDATION_UNAVAILABLE"}
        code = 1
    print(json.dumps(payload, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
