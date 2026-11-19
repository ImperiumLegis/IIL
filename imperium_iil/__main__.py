"""Offline validator CLI. All proposed resource paths remain data."""

import argparse
import json
from pathlib import Path
import sys

EXIT_CODES = {"READY_FOR_REVIEW": 0, "NEEDS_CLARIFICATION": 2, "UNSUPPORTED": 3, "INVALID": 4}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review an IIL proposal using synthetic demo context.")
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("proposal", type=Path)
    args = parser.parse_args(argv)
    try:
        from .context import load_demo_context
        from .validator import PROPOSAL_LIMIT, validate

        context = load_demo_context()
        with args.proposal.open("rb") as stream:
            result = validate(stream.read(PROPOSAL_LIMIT + 1), context)
        payload = result.as_dict()
        code = EXIT_CODES[result.status]
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
