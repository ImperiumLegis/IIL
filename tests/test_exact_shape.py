import json
from copy import deepcopy
from pathlib import Path

import pytest

from imperium_iil import structure
from imperium_iil.context import load_context
from imperium_iil.parser import ParseError, parse_bytes


@pytest.fixture
def proposal():
    return {
        "iil_version": "0.2",
        "draft_id": "edit",
        "task": {"description": "Update the guide."},
        "context": {
            "catalog": {"id": "exact-update-catalog", "version": "1"},
            "policy": {"id": "exact-update-policy", "version": "1"},
            "registry": {"id": "exact-update-registry", "version": "0.2"},
        },
        "operations": [{
            "id": "op", "capability": "github.file.update",
            "resource": {"type": "github.file", "repository_id": "repo-demo", "branch": "main",
                         "revision": "a" * 40, "path": "docs/guide.md"},
            "replacement": {"text": "Edit.\n"},
        }],
        "restrictions": [], "unresolved": [], "evidence_refs": [],
    }


def statuses(document):
    return {f.status for f in structure.check_exact_shape(document)}


def test_context_binds_exact_registry_and_eligible_guide(proposal):
    root = Path(__file__).resolve().parents[1]
    context = load_context((root / "fixtures/exact-update-context.json").read_bytes())
    assert context.refs == proposal["context"]
    snapshot = context.snapshots["repo-demo", "main"]
    for capability in ("github.file.update", "github.file.read"):
        assert "docs/guide.md" in snapshot["eligible"][capability]


@pytest.mark.parametrize("text,expected", [
    ("", set()), ("\t\n ~", set()), ("x" * 16384, set()), ("x" * 16385, {"INVALID"}),
    ("\r", {"UNSUPPORTED"}), ("\x00", {"UNSUPPORTED"}), ("\x7f", {"UNSUPPORTED"}),
    ("é", {"UNSUPPORTED"}), ("é" * 8192 + "x", {"INVALID"}),
], ids=["empty", "tab-lf", "byte-limit", "too-large", "cr", "nul", "del", "unicode",
        "multibyte-over-limit"])
def test_decoded_text_bounds(proposal, text, expected):
    proposal["operations"][0]["replacement"]["text"] = text
    parsed = parse_bytes(json.dumps(proposal).encode(), limit=65536)
    assert statuses(parsed) == expected


def test_unpaired_surrogate_is_parser_failure(proposal):
    proposal["operations"][0]["replacement"]["text"] = "\ud800"
    with pytest.raises(ParseError, match="INVALID_UNICODE"):
        parse_bytes(json.dumps(proposal).encode(), limit=65536)


@pytest.mark.parametrize("replacement", [None, {}, {"text": False}, {"text": "x", "approved": True}])
def test_invalid_replacement(proposal, replacement):
    proposal["operations"][0]["replacement"] = replacement
    assert statuses(proposal) == {"INVALID"}


def test_missing_replacement(proposal):
    del proposal["operations"][0]["replacement"]
    assert statuses(proposal) == {"INVALID"}


@pytest.mark.parametrize("key", ["fingerprint", "approved", "review"])
def test_closed_document(proposal, key):
    proposal[key] = "forged"
    assert statuses(proposal) == {"INVALID"}


def test_empty_operations(proposal):
    proposal["operations"] = []
    assert statuses(proposal) == {"NEEDS_CLARIFICATION"}


def test_multiple_operations_still_require_valid_structure(proposal):
    second = deepcopy(proposal["operations"][0])
    second["id"] = "second"
    second["resource"]["path"] = "docs/other.md"
    proposal["operations"].append(second)
    assert statuses(proposal) == {"UNSUPPORTED"}
    second["replacement"] = {}
    assert statuses(proposal) == {"INVALID"}


def test_other_capabilities_still_require_valid_structure(proposal):
    op = proposal["operations"][0]
    op["capability"] = "github.file.read"
    del op["replacement"]
    assert statuses(proposal) == {"UNSUPPORTED"}
    del op["resource"]["branch"]
    assert statuses(proposal) == {"INVALID"}


def test_profile_dispatch(proposal):
    assert {f.status for f in structure.check_shape(proposal)} == {"UNSUPPORTED"}
    proposal["iil_version"] = "0.1"
    assert statuses(proposal) == {"UNSUPPORTED"}
