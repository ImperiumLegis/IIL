"""Load offline catalog, registry and policy data independently of proposals."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from .resources import resource_dir
from types import MappingProxyType

from jsonschema import Draft202012Validator

from .parser import ParseError, parse_bytes
from .structure import valid_path


_MAX_BYTES = 1_048_576
_FILE_CAPABILITIES = {"github.file.read", "github.file.update", "github.file.delete"}
_PR = "github.pull_request.create"


class ContextError(ValueError):
    """The operator-supplied context could not be loaded or validated."""


@cache
def _schema():
    path = resource_dir("schemas") / "context-v0.1.schema.json"
    return Draft202012Validator(json.loads(path.read_bytes()))


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _registry(records):
    if not (_FILE_CAPABILITIES | {_PR}) <= records.keys():
        raise ContextError("Incomplete v0.1 registry")
    capabilities = {}
    for name, record in records.items():
        supported = name in _FILE_CAPABILITIES
        if record["supported"] != supported:
            raise ContextError("Invalid v0.1 capability disposition")
        if supported and record["resource_type"] != "github.file":
            raise ContextError("Invalid file capability resource type")
        if name == _PR and record["resource_type"] != "github.pull_request":
            raise ContextError("Invalid pull request resource type")
        capabilities[name] = supported
    return capabilities


def _snapshots(bundle, capabilities):
    repositories = bundle["repositories"]
    identities = {(record["host"], record["provider_id"]) for record in repositories.values()}
    if len(identities) != len(repositories):
        raise ContextError("Conflicting provider repository mappings")
    snapshots = {}
    for snapshot in bundle["snapshots"]:
        repo = snapshot["repository_id"]
        key = (repo, snapshot["branch"])
        if repo not in repositories or key in snapshots:
            raise ContextError("Missing repository or conflicting snapshot")
        files = snapshot["files"]
        if not all(valid_path(path) for path in files):
            raise ContextError("Invalid catalog path")
        for path in files:
            parts = path.split("/")
            if any("/".join(parts[:i]) in files for i in range(1, len(parts))):
                raise ContextError("Catalog file is also used as a directory")
        for name, paths in snapshot["eligible"].items():
            if not capabilities.get(name) or any(files.get(p) != "regular" for p in paths):
                raise ContextError("Invalid capability envelope")
        for group in snapshot["groups"].values():
            if group["review_ref"] not in bundle["evidence"] or not files.keys() >= set(group["members"]):
                raise ContextError("Dangling classification reference")
        snapshots[key] = snapshot
    return snapshots


def _check_denials(bundle, capabilities, snapshots):
    for rule in bundle["denials"]:
        repo = rule["repository_id"]
        if repo not in bundle["repositories"] or not capabilities.keys() >= set(rule["capabilities"]):
            raise ContextError("Dangling policy rule reference")
        selector = rule["selector"]
        kind, value = selector["kind"], selector["value"]
        if kind == "catalog_group":
            targets = [s for (r, _), s in snapshots.items() if r == repo]
            if not targets or any(value not in s["groups"] for s in targets):
                raise ContextError("Dangling policy classification")
        elif not valid_path(value) or (kind == "basename" and "/" in value):
            raise ContextError("Invalid policy selector")


@dataclass(frozen=True, slots=True, init=False, eq=False)
class TrustedContext:
    refs: Mapping
    capabilities: Mapping
    repositories: Mapping
    snapshots: Mapping
    evidence: Mapping
    denials: tuple

    def __init__(self, raw: bytes):
        if not isinstance(raw, bytes):
            raise ContextError("Expected context bytes")
        try:
            bundle = parse_bytes(raw, limit=_MAX_BYTES)
            valid = _schema().is_valid(bundle)
        except (ParseError, OSError, json.JSONDecodeError) as exc:
            raise ContextError("Cannot decode context or local schema") from exc
        if not valid:
            raise ContextError("Invalid trusted context structure")
        capabilities = _registry(bundle["capabilities"])
        snapshots = _snapshots(bundle, capabilities)
        _check_denials(bundle, capabilities, snapshots)
        evidence = {key: record["status"] for key, record in bundle["evidence"].items()}
        for name, value in (
            ("refs", bundle["refs"]),
            ("capabilities", capabilities),
            ("repositories", bundle["repositories"]),
            ("snapshots", snapshots),
            ("evidence", evidence),
            ("denials", bundle["denials"]),
        ):
            object.__setattr__(self, name, _freeze(value))


def load_context(raw: bytes) -> TrustedContext:
    return TrustedContext(raw)


def load_demo_context() -> TrustedContext:
    try:
        with (resource_dir("fixtures") / "demo-context.json").open("rb") as source:
            raw = source.read(_MAX_BYTES + 1)
    except OSError as exc:
        raise ContextError("Cannot read bundled synthetic context") from exc
    return load_context(raw)
