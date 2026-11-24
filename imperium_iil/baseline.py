"""Load exact before-text from the operator's bounded offline inventory."""

import json
from functools import cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .context import ContextError, TrustedContext
from .parser import ParseError, parse_bytes
from .resources import resource_dir
from .structure import exact_text_error


@cache
def _schema(extended):
    directory = resource_dir("schemas")
    legacy = json.loads((directory / "before-text-v1.schema.json").read_bytes())
    if extended:
        registry = Registry().with_resource("urn:imperium:before-text:1", Resource.from_contents(legacy))
        schema = json.loads((directory / "before-text-v2.schema.json").read_bytes())
        return Draft202012Validator(schema, registry=registry)
    return Draft202012Validator(legacy)


def load_baseline(raw: bytes, context: TrustedContext, *,
                  allow_utf8: bool = False) -> dict[tuple[str, str, str, str], str]:
    if not isinstance(raw, bytes):
        raise ContextError("Expected before-text bytes")
    try:
        inventory = parse_bytes(raw, limit=1_048_576)
        extended = allow_utf8 and inventory.get("format_version") == "2"
        valid = _schema(extended).is_valid(inventory)
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
        if exact_text_error(text, "0.3" if extended else "0.2"):
            raise ContextError("Invalid before-text representation")
        index[key] = text
    return index
