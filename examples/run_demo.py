"""Run the public CLI on all nine synthetic fixtures from a local checkout."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "valid/read_docs": ("READY_FOR_REVIEW", 0),
    "clarification/cleanup": ("NEEDS_CLARIFICATION", 2),
    "valid/update_docs": ("READY_FOR_REVIEW", 0),
    "unsupported/admin": ("UNSUPPORTED", 3),
    "invalid/protected": ("INVALID", 4),
    "invalid/forged_approval": ("INVALID", 4),
    "invalid/duplicate_key": ("INVALID", 4),
    "invalid/hidden_effect": ("INVALID", 4),
    "valid/prose_mismatch": ("READY_FOR_REVIEW", 0),
}


def main():
    print("Imperium Intent Language 0.1 | synthetic repository | offline review")
    print(f"{'Proposal':28} {'Verdict':22} Findings")
    for name, (status, code) in EXPECTED.items():
        run = subprocess.run(
            [sys.executable, "-m", "imperium_iil", "validate", f"examples/{name}.json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        result = json.loads(run.stdout)
        reasons = sorted({item["code"] for item in result.get("findings", [])})
        print(f"{name:28} {result['status']:22} {', '.join(reasons) or '-'}")
        if (result["status"], run.returncode) != (status, code) or result["authority_granted"] is not False:
            return 1
    print("9/9 expected verdicts. Authority granted: false in every case.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
