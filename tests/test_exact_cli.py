import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "examples" / "exact-update"


def review(path, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", "imperium_iil", "review", str(path)],
        cwd=cwd, capture_output=True, check=False,
    )


def test_compare_and_replay_exact_edits():
    paths = [GUIDES / f"guide-{letter}.json" for letter in ("a", "b")]
    runs = [review(path) for path in paths]
    artifacts = []
    for step, run in enumerate(runs, start=1):
        assert run.returncode == 0, (run.stdout, run.stderr)
        assert run.stderr == b""
        payload = json.loads(run.stdout)
        assert payload["status"] == "READY_FOR_REVIEW"
        assert payload["authority_granted"] is False
        artifact = payload["review"]
        assert artifact["after"] == f"Run step {step} from the repository root.\n"
        assert artifact["target"]["path"] == "docs/guide.md"
        artifacts.append(artifact)

    first, second = (path.read_bytes() for path in paths)
    assert len(first) == len(second)
    assert sum(a != b for a, b in zip(first, second)) == 1
    assert artifacts[0]["before"] == artifacts[1]["before"]
    assert artifacts[0]["fingerprint"] != artifacts[1]["fingerprint"]
    assert review(paths[0]).stdout == runs[0].stdout


def test_review_missing_input_is_sanitized(tmp_path):
    run = review(tmp_path / "private-proposal-name.json")
    assert run.returncode == 1 and run.stderr == b""
    assert json.loads(run.stdout) == {
        "status": "OPERATIONAL_ERROR", "authority_granted": False,
        "code": "INPUT_OR_CONTEXT_UNAVAILABLE",
    }


def test_review_broken_trusted_input_is_sanitized(tmp_path):
    for directory in ("imperium_iil", "fixtures", "schemas"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    (tmp_path / "fixtures" / "demo-before-text.json").write_bytes(b"private baseline marker")
    run = review(GUIDES / "guide-a.json", cwd=tmp_path)
    assert run.returncode == 1 and run.stderr == b""
    assert json.loads(run.stdout) == {
        "status": "OPERATIONAL_ERROR", "authority_granted": False,
        "code": "INPUT_OR_CONTEXT_UNAVAILABLE",
    }
