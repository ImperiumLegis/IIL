import json
from hashlib import sha256
from pathlib import Path

import pytest

from imperium_iil import __version__, approval, match_call
from imperium_iil.context import ContextError
from imperium_iil.match_call import compare_call
from imperium_iil.review import review_update
from imperium_iil.tool_call import parse_update_call
from test_approval import Terminal
from test_receipt_cli import issue, setup


ROOT = Path(__file__).resolve().parents[1]
LIMIT = 256 * 1024


@pytest.fixture
def inputs():
    proposal = json.loads((ROOT / "examples/exact-update/guide-a.json").read_bytes())
    proposal["iil_version"] = "0.3"
    context = json.loads((ROOT / "fixtures/exact-update-context.json").read_bytes())
    baseline = json.loads((ROOT / "fixtures/demo-before-text.json").read_bytes())
    return proposal, context, baseline


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode()


def review(inputs, after):
    inputs[0]["operations"][0]["replacement"]["text"] = after
    return review_update(*(encode(item) for item in inputs))


def test_utf8_preserves_original_bytes_and_line_endings(inputs):
    before = "Caf\u00e9\r\n"
    after = "Cafe\u0301\r\n\U0001f469\u200d\U0001f4bb\n"
    baseline = inputs[2]
    baseline["format_version"] = "2"
    baseline["entries"][0]["text"] = before
    result = review(inputs, after)
    assert result["validator_version"] == __version__
    artifact = result["review"]
    assert artifact["format_version"] == "2"
    assert artifact["before"] == before and artifact["after"] == after
    assert artifact["task"] == inputs[0]["task"]
    assert artifact["after_sha256"] == sha256(after.encode()).hexdigest()
    assert artifact["before_sha256"] == sha256(before.encode()).hexdigest()
    assert artifact["before_bytes"] == len(before.encode())
    assert artifact["after_bytes"] == len(after.encode())
    for changed in (after.replace("\r\n", "\n"), after.rstrip("\n"), after.replace("e\u0301", "\u00e9")):
        assert review(inputs, changed)["review"]["fingerprint"] != artifact["fingerprint"]


def test_multibyte_limit_and_v1_baseline_compatibility(inputs):
    text = "\U0001f642" * (LIMIT // 4)
    assert review(inputs, text)["review"]["after_bytes"] == LIMIT
    result = review(inputs, text + "a")
    assert result["status"] == "INVALID" and "review" not in result
    inputs[2]["format_version"] = "2"
    inputs[2]["entries"][0]["text"] = text + "a"
    with pytest.raises(ContextError):
        review(inputs, "ok")


def test_utf8_profile_keeps_nontext_structure_bounded(inputs):
    inputs[0]["evidence_refs"] = [None] * 8000
    result = review(inputs, "ok")
    assert result["status"] == "INVALID"
    assert [finding["code"] for finding in result["findings"]] == ["STRUCTURE_LIMIT"]


def test_malformed_trusted_inventory_takes_precedence(inputs):
    with pytest.raises(ContextError):
        review_update(b"broken proposal", encode(inputs[1]), b"broken baseline")


def test_v02_keeps_original_envelope_and_inventory_limits(inputs):
    inputs[0]["iil_version"] = "0.2"
    result = review_update(encode(inputs[0]).ljust(65537), encode(inputs[1]), encode(inputs[2]))
    assert result["findings"][0]["code"] == "INPUT_TOO_LARGE"
    inputs[2]["format_version"] = "2"
    with pytest.raises(ContextError):
        review(inputs, "ok")


@pytest.mark.parametrize("bad", ["\x00", "\x1b", "\x7f", "\x85", "\u202e", "\u2066", "\r"])
def test_controls_do_not_produce_a_review(inputs, bad):
    result = review(inputs, "x" + bad + "y")
    assert result["status"] == "UNSUPPORTED" and "review" not in result


def test_dense_line_input_omits_only_optional_diff(inputs):
    text = "\n" * LIMIT
    artifact = review(inputs, text)["review"]
    assert artifact["after"] == text
    assert "diff" not in artifact and artifact["diff_omitted"] == "LINE_LIMIT"


def test_cli_confirmation_escapes_newlines_and_non_ascii(inputs, tmp_path):
    after = "\U0001f642\r\n" + "x" * 70000
    inputs[0]["operations"][0]["replacement"]["text"] = after
    path = tmp_path / "proposal.json"
    path.write_bytes(encode(inputs[0]))
    output = Terminal()
    assert approval.compare_in_session(path, path, Terminal("APPROVE\n"), output) == "APPROVAL_MATCHED"
    rendered = output.getvalue()
    assert rendered.isascii() and "\r" not in rendered
    assert r"\ud83d\ude42\r\n" in rendered


def test_match_checks_profile_and_exact_utf8_bytes(inputs):
    doc = json.loads((ROOT / "examples/tool-calls/guide-a.json").read_bytes())
    repo = inputs[1]["repositories"]["repo-demo"]
    doc["version"] = "2"
    after = "\u00e9\r\n" + "x" * 70000
    doc["arguments"]["text"] = after
    artifact = review(inputs, after)["review"]
    compare_call(parse_update_call(encode(doc)), artifact, repo)
    doc["arguments"]["text"] = after.replace("\r\n", "\n")
    with pytest.raises(ValueError):
        compare_call(parse_update_call(encode(doc)), artifact, repo)
    doc["arguments"]["text"] = "ascii"
    doc["version"] = "1"
    with pytest.raises(ValueError):
        compare_call(parse_update_call(encode(doc)), review(inputs, "ascii")["review"], repo)


def test_signed_unicode_update_matches_escaped_tool_call(inputs, setup, tmp_path, monkeypatch, capsys):
    args, trust, _, signed = setup
    text = "x" * 70000 + "Cafe\u0301 \U0001f642\r\n"
    inputs[0]["operations"][0]["replacement"]["text"] = text
    proposal = tmp_path / "utf8.json"
    proposal.write_bytes(encode(inputs[0]))
    args[1] = str(proposal)
    code, preview = issue(args, monkeypatch, "APPROVE\n")
    assert code == 0 and r"\ud83d\ude42\r\n" in preview
    capsys.readouterr()
    doc = json.loads((ROOT / "examples/tool-calls/guide-a.json").read_bytes())
    doc["version"] = "2"
    doc["arguments"]["text"] = text
    call_path = tmp_path / "utf8-call.json"
    call_path.write_bytes(json.dumps(doc, ensure_ascii=True).encode())
    cli = [str(proposal), "--call", str(call_path), "--receipt", str(signed), "--trust", str(trust)]
    assert match_call.main(cli) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "TOOL_CALL_MATCHED", "authority_granted": False}
