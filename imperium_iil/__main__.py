"""Offline validator CLI. All proposed resource paths remain data."""

import argparse
import json
from pathlib import Path
import sys

EXIT_CODES = {"READY_FOR_REVIEW": 0, "NEEDS_CLARIFICATION": 2, "UNSUPPORTED": 3, "INVALID": 4}
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_LIMIT = 1_048_576


def _read(path, limit):
    with path.open("rb") as stream:
        return stream.read(limit + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review an IIL proposal using synthetic demo context.")
    parser.add_argument("command", choices=["validate", "review"])
    parser.add_argument("proposal", type=Path)
    args = parser.parse_args(argv)
    try:
        from .context import load_demo_context
        from .validator import PROPOSAL_LIMIT, validate

        proposal = _read(args.proposal, PROPOSAL_LIMIT)
        if args.command == "review":
            from .review import review_update

            context = _read(FIXTURES / "exact-update-context.json", FIXTURE_LIMIT)
            baseline = _read(FIXTURES / "demo-before-text.json", FIXTURE_LIMIT)
            payload = review_update(proposal, context, baseline)
        else:
            payload = validate(proposal, load_demo_context()).as_dict()
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
