"""Compare two synthetic organizations through the public validator API."""

from pathlib import Path

from imperium_iil.context import load_context
from imperium_iil.validator import validate


ROOT = Path(__file__).resolve().parents[1]


def main():
    docs_request = (ROOT / "examples/valid/update_docs.json").read_bytes()
    release_request = (ROOT / "examples/invalid/release_team_update.json").read_bytes()
    docs_team = load_context((ROOT / "fixtures/demo-context.json").read_bytes())
    release_team = load_context((ROOT / "fixtures/release-team-context.json").read_bytes())
    print("Requested change: update docs/guide.md")
    for label, proposal, context, status, reason in (
        ("Documentation team", docs_request, docs_team, "READY_FOR_REVIEW", None),
        ("Release team", release_request, release_team, "INVALID", "POLICY_CONFLICT"),
        ("Documentation proposal under release policy", docs_request, release_team,
         "NEEDS_CLARIFICATION", "CONTEXT_MISMATCH"),
    ):
        result = validate(proposal, context)
        codes = {item.code for item in result.findings}
        print(f"{label}: {result.status} ({', '.join(sorted(codes)) or 'no findings'})")
        if result.status != status or result.authority_granted or (reason and reason not in codes):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
