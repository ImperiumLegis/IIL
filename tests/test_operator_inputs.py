import json
from pathlib import Path

from imperium_iil.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def test_operator_context_and_baseline(tmp_path, capsys):
    assert main(["validate", str(ROOT/"examples/valid/update_docs.json"),
                 "--context", str(ROOT/"fixtures/release-team-context.json")]) != 0
    capsys.readouterr()
    baseline = json.loads((ROOT/"fixtures/demo-before-text.json").read_bytes())
    baseline["entries"][0]["text"] = "Operator input\n"
    path = tmp_path/"before.json"
    path.write_text(json.dumps(baseline))
    assert main(["review", str(ROOT/"examples/exact-update/guide-a.json"),
                 "--context", str(ROOT/"fixtures/exact-update-context.json"), "--baseline", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["review"]["before"] == "Operator input\n"
