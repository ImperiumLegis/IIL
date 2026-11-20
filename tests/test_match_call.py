import json
import subprocess
import sys

import pytest

from imperium_iil import match_call
from imperium_iil.receipts import parse_time
from test_receipt_cli import A, B, ROOT, issue, setup


@pytest.fixture
def inputs(setup, monkeypatch, tmp_path, capsys):
    args, trust, _, signed = setup
    assert issue(args, monkeypatch, "APPROVE\n")[0] == 0
    capsys.readouterr()
    paths = {"proposal": tmp_path / "proposal.json", "receipt": signed,
             "trust": trust, "call": tmp_path / "call.json",
             "context": tmp_path / "context.json", "baseline": tmp_path / "baseline.json"}
    paths["proposal"].write_bytes(A.read_bytes())
    for name, fixture in (("context", "exact-update-context.json"), ("baseline", "demo-before-text.json")):
        paths[name].write_bytes((ROOT / "fixtures" / fixture).read_bytes())
    paths["call"].write_bytes((ROOT / "examples/tool-calls/guide-a.json").read_bytes())
    return paths


def cli(paths):
    args = [str(paths["proposal"])]
    for name in ("call", "receipt", "context", "baseline", "trust"):
        args.extend(["--" + name, str(paths[name])])
    return args


def rejected(paths, capsys):
    assert match_call.main(cli(paths)) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "TOOL_CALL_REJECTED", "authority_granted": False}
    assert captured.err == ""


@pytest.mark.parametrize("field", ["host", "provider_id", "branch", "base_revision", "path", "text",
                                   "newline", "unknown", "tool"])
def test_changed_call(inputs, field, capsys):
    doc = json.loads(inputs["call"].read_bytes())
    if field == "newline":
        doc["arguments"]["text"] = doc["arguments"]["text"].rstrip("\n")
    elif field == "tool":
        doc["tool"] = "delete_file"
    else:
        doc["arguments"][field] = "private-marker"
    inputs["call"].write_text(json.dumps(doc))
    rejected(inputs, capsys)


@pytest.mark.parametrize("change", ["proposal", "baseline", "context", "remap", "denial", "signature"])
def test_changed_signed_inputs(inputs, change, capsys):
    if change in ("proposal", "baseline", "context"):
        with inputs[change].open("ab") as stream:
            stream.write(b" ")
    elif change == "signature":
        doc = json.loads(inputs["receipt"].read_bytes())
        doc["signature"] = "AAAA"
        inputs["receipt"].write_text(json.dumps(doc))
    else:
        doc = json.loads(inputs["context"].read_bytes())
        if change == "remap":
            doc["repositories"]["repo-demo"]["provider_id"] = "2002"
        else:
            doc["denials"].append({"repository_id": "repo-demo", "capabilities": ["github.file.update"],
                                   "selector": {"kind": "exact_path", "value": "docs/guide.md"}})
        inputs["context"].write_text(json.dumps(doc))
    rejected(inputs, capsys)


@pytest.mark.parametrize("change", ["revoke_during_read", "swap_after_read"])
def test_input_snapshot(inputs, change, monkeypatch, capsys):
    original = match_call._read
    if change == "swap_after_read":
        inputs["call"].write_bytes((ROOT / "examples/tool-calls/guide-b.json").read_bytes())
    reads = []
    def read(path, limit):
        data = original(path, limit)
        reads.append(path)
        if path == inputs["call"] and change == "revoke_during_read":
            doc = json.loads(inputs["trust"].read_bytes())
            doc["reviewers"][0]["grants"] = []
            inputs["trust"].write_text(json.dumps(doc))
        if path == inputs["proposal"] and change == "swap_after_read":
            path.write_bytes(B.read_bytes())
        return data
    monkeypatch.setattr(match_call, "_read", read)
    rejected(inputs, capsys)
    assert reads == [inputs[k] for k in ("call", "proposal", "receipt", "context", "baseline", "trust")]


def test_expiry_at_final_check(inputs, capsys, monkeypatch):
    record = json.loads(inputs["receipt"].read_bytes())
    times = iter(parse_time(record[k]) for k in ("issued_at", "expires_at"))
    monkeypatch.setattr(match_call, "now", lambda: next(times))
    rejected(inputs, capsys)
    assert next(times, None) is None


@pytest.mark.parametrize("name,expected", [("guide-a", "TOOL_CALL_MATCHED"), ("guide-b", "TOOL_CALL_REJECTED")])
def test_demo_in_fresh_process(inputs, name, expected):
    inputs["call"] = ROOT / f"examples/tool-calls/{name}.json"
    run = subprocess.run([sys.executable, "-m", "imperium_iil.match_call", *cli(inputs)],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == (0 if name == "guide-a" else 1)
    assert json.loads(run.stdout) == {"status": expected, "authority_granted": False}
    assert run.stderr == ""
