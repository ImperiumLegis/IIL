"""Load exact before-text from the operator's bounded offline inventory."""

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator

from .context import ContextError, TrustedContext
from .parser import ParseError, parse_bytes
from .structure import EXACT_TEXT_LIMIT, supported_exact_text


@cache
def _schema():
    path = Path(__file__).resolve().parents[1] / "schemas" / "before-text-v1.schema.json"
    return Draft202012Validator(json.loads(path.read_bytes()))


def load_baseline(raw: bytes, context: TrustedContext) -> dict[tuple[str, str, str, str], str]:
    if not isinstance(raw, bytes):
        raise ContextError("Expected before-text bytes")
    try:
        inventory = parse_bytes(raw, limit=1_048_576)
        valid = _schema().is_valid(inventory)
    except (ParseError, OSError, json.JSONDecodeError) as exc:
        raise ContextError("Cannot decode before-text inventory or local schema") from exc
    if not valid:
        raise ContextError("Invalid before-text structure")
    if inventory["catalog_ref"] != context.refs["catalog"]:
        raise ContextError("Before-text catalog reference mismatch")

    index = {}
    for entry in inventory["entries"]:
        repo, branch = entry["repository_id"], entry["branch"]
        revision, path = entry["revision"], entry["path"]
        snapshot = context.snapshots.get((repo, branch))
        if (snapshot is None or snapshot["revision"] != revision
                or snapshot["files"].get(path) != "regular"):
            raise ContextError("Before-text entry has no matching regular file in the snapshot")
        key = (repo, branch, revision, path)
        if key in index:
            raise ContextError("Duplicate before-text entry")
        text = entry["text"]
        if len(text.encode("utf-8")) > EXACT_TEXT_LIMIT or not supported_exact_text(text):
            raise ContextError("Invalid before-text representation")
        index[key] = text
    return index
