import json
from pathlib import Path

import pytest

from imperium_iil.baseline import load_baseline
from imperium_iil.context import ContextError, load_context


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GUIDE = ("repo-demo", "main", "a" * 40, "docs/guide.md")


def encode(value):
    return json.dumps(value).encode()


@pytest.fixture
def bundle():
    return json.loads((FIXTURES / "exact-update-context.json").read_bytes())


@pytest.fixture
def context(bundle):
    return load_context(encode(bundle))


@pytest.fixture
def inventory():
    return {
        "format_version": "1",
        "catalog_ref": {"id": "exact-update-catalog", "version": "1"},
        "entries": [{
            "repository_id": "repo-demo", "branch": "main", "revision": "a" * 40,
            "path": "docs/guide.md", "text": "Run the demo.\n",
        }],
    }


def test_demo_before_text(context):
    raw = (FIXTURES / "demo-before-text.json").read_bytes()
    assert load_baseline(raw, context) == {GUIDE: "Run the demo.\n"}


def test_empty_inventory_and_raw_size_limit(inventory, context):
    inventory["entries"] = []
    raw = encode(inventory).ljust(1_048_576, b" ")
    assert load_baseline(raw, context) == {}
    with pytest.raises(ContextError):
        load_baseline(raw + b" ", context)


def test_snapshots_with_the_same_path(bundle, inventory):
    second = {"branch": "release", "revision": "b" * 40}
    bundle["snapshots"].append({**bundle["snapshots"][0], **second})
    inventory["entries"].append({**inventory["entries"][0], **second, "text": ""})
    context = load_context(encode(bundle))
    assert load_baseline(encode(inventory), context) == {
        GUIDE: "Run the demo.\n",
        ("repo-demo", "release", "b" * 40, "docs/guide.md"): "",
    }


@pytest.mark.parametrize("field,value", [
    ("revision", "b" * 40), ("branch", "release"), ("repository_id", "other"),
    ("path", "absent"), ("path", "guide-link"), ("unexpected", True),
    ("text", "a" * 16_385), ("text", "\u00e9"), ("text", "\r\n"),
    ("text", "\x00"), ("text", "\x7f"), ("text", None),
], ids=["revision", "branch", "repo", "path", "symlink", "entry-field", "too-long",
        "unicode", "crlf", "nul", "del", "null"])
def test_invalid_entry_is_an_operational_error(inventory, context, field, value):
    inventory["entries"][0][field] = value
    with pytest.raises(ContextError):
        load_baseline(encode(inventory), context)


def test_text_at_limit_preserves_tabs_and_final_newline(inventory, context):
    text = " ~" * 8191 + "\t\n"
    inventory["entries"][0]["text"] = text
    assert load_baseline(encode(inventory), context)[GUIDE] == text


@pytest.mark.parametrize("fields", [
    {"format_version": "2"}, {"extra": True}, {"catalog_ref": {"id": "demo-catalog", "version": "1"}},
    {"catalog_ref": {"id": "exact-update-catalog", "version": "2"}},
])
def test_rejects_invalid_inventory_header(inventory, context, fields):
    inventory.update(fields)
    with pytest.raises(ContextError):
        load_baseline(encode(inventory), context)


def test_duplicate_file_identity(inventory, context):
    inventory["entries"].append({**inventory["entries"][0], "text": "conflict"})
    with pytest.raises(ContextError):
        load_baseline(encode(inventory), context)


def test_duplicate_json_key(inventory, context):
    raw = encode(inventory).replace(b'"text":', b'"text": "ignored", "text":')
    with pytest.raises(ContextError):
        load_baseline(raw, context)
