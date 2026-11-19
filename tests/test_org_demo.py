import json

from examples.compare_policies import ROOT, main


def test_org_demo_changes_only_context_and_checks_verdicts():
    docs = json.loads((ROOT / "examples/valid/update_docs.json").read_bytes())
    release = json.loads((ROOT / "examples/invalid/release_team_update.json").read_bytes())
    assert docs.pop("context") != release.pop("context")
    assert docs == release
    assert main() == 0
