"""Human confirmation for one offline exact-update comparison."""

import argparse
import json
from pathlib import Path
import sys

from .__main__ import FIXTURES, FIXTURE_LIMIT, _read
from .review import EXACT_PROPOSAL_LIMIT, review_update


def _review(path):
    return review_update(
        _read(path, EXACT_PROPOSAL_LIMIT),
        _read(FIXTURES / "exact-update-context.json", FIXTURE_LIMIT),
        _read(FIXTURES / "demo-before-text.json", FIXTURE_LIMIT),
    )


def compare_in_session(reviewed, submitted, terminal_in, terminal_out):
    """The operator controls the terminal, interpreter, and fixture directory."""
    if not terminal_in.isatty() or not terminal_out.isatty():
        return "REVIEW_TERMINAL_REQUIRED"
    preview = _review(reviewed)
    if preview["status"] != "READY_FOR_REVIEW":
        return "REVIEW_BLOCKED"
    artifact = preview["review"]
    print(json.dumps(artifact, ensure_ascii=True, indent=2), file=terminal_out)
    print("Type APPROVE to confirm this exact edit: ", end="", file=terminal_out, flush=True)
    if terminal_in.readline(16).rstrip("\r\n") != "APPROVE":
        return "APPROVAL_DECLINED"
    candidate = _review(submitted)
    if candidate["status"] != "READY_FOR_REVIEW":
        return "SUBMISSION_BLOCKED"
    if candidate["review"]["fingerprint"] != artifact["fingerprint"]:
        return "FRESH_REVIEW_REQUIRED"
    return "APPROVAL_MATCHED"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Confirm and compare one exact edit offline.")
    parser.add_argument("reviewed", type=Path)
    parser.add_argument("submitted", type=Path)
    args = parser.parse_args(argv)
    try:
        status = compare_in_session(args.reviewed, args.submitted, sys.stdin, sys.stderr)
    except (OSError, ValueError):
        status = "INPUT_OR_CONTEXT_UNAVAILABLE"
    print(json.dumps({"status": status, "authority_granted": False}))
    return 0 if status == "APPROVAL_MATCHED" else 1


if __name__ == "__main__":
    sys.exit(main())
