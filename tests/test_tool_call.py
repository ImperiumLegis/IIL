import json

import pytest

from imperium_iil.tool_call import parse_update_call


def envelope():
    return {"version": "1", "tool": "update_file", "arguments": {
        "host": "github.example", "provider_id": "1001", "branch": "main",
        "base_revision": "a" * 40, "path": "docs/guide.md", "text": "a\n"}}


def test_adapter_and_encoding():
    raw = json.dumps(envelope()).encode()
    op = parse_update_call(raw)
    assert op.action == "github.file.update" and op.text == b"a\n"
    assert parse_update_call(raw.replace(b"a\\n", br"\u0061\u000a")) == op
    assert parse_update_call(raw.ljust(65536)) == op
    with pytest.raises(ValueError):
        parse_update_call(raw.ljust(65537))


@pytest.mark.parametrize("case", ["missing", "missing_arg", "extra", "extra_arg", "tool", "version",
                                  "type", "actions", "oversize", "control", "duplicate", "incomplete"])
def test_reject_envelope(case):
    doc = envelope()
    args = doc["arguments"]
    if case == "missing":
        del doc["version"]
    elif case == "missing_arg":
        del args["base_revision"]
    elif case == "extra":
        doc["next"] = doc.copy()
    elif case == "extra_arg":
        args["force"] = True
    elif case == "tool":
        doc["tool"] = "delete_file"
    elif case == "version":
        doc["version"] = "2"
    elif case == "type":
        args["text"] = None
    elif case == "actions":
        doc = [doc, doc]
    elif case == "oversize":
        args["text"] = "a" * 16385
    elif case == "control":
        args["text"] = "\r"
    raw = json.dumps(doc).encode()
    if case == "duplicate":
        raw = raw.replace(b'"text":', br'"te\u0078t":"x","text":')
    if case == "incomplete":
        raw = raw[:-1]
    with pytest.raises(ValueError):
        parse_update_call(raw)


def test_text_boundary():
    doc = envelope()
    doc["arguments"]["text"] = "a" * 16384
    assert len(parse_update_call(json.dumps(doc).encode()).text) == 16384
