"""Local, digest-pinned action descriptions. All extension inputs are data."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PureWindowsPath

from .__main__ import _read
from .action_types import bound, typed_fields
from .parser import parse_bytes
from .reviewer_trust import fields, identifier, matches, require
from .structure import supported_exact_text

LIMIT = 65536


def document(raw, *, numbers=False):
    return parse_bytes(raw, limit=LIMIT, numbers=numbers)


def read(path):
    raw = _read(path, LIMIT)
    require(len(raw) <= LIMIT)
    return raw


@dataclass(frozen=True)
class Field:
    minimum: int
    maximum: int
    cardinality: tuple | None

    @classmethod
    def parse(cls, spec):
        require(isinstance(spec, dict) and spec.get("type") in ("string", "list"))
        is_list = spec["type"] == "list"
        fields(spec, ("type", "min", "max", "least", "most") if is_list else ("type", "min", "max"))
        low, high = bound(spec["min"], 16384), bound(spec["max"], 16384)
        require(low <= high)
        counts = None
        if is_list:
            counts = bound(spec["least"], 64), bound(spec["most"], 64)
            require(counts[0] <= counts[1])
        return cls(low, high, counts)

    def check(self, value):
        values = [value]
        if self.cardinality is not None:
            low, high = self.cardinality
            require(isinstance(value, list) and low <= len(value) <= high)
            values = value
        for item in values:
            require(isinstance(item, str) and supported_exact_text(item))
            require(self.minimum <= len(item.encode("utf-8")) <= self.maximum)


@dataclass(frozen=True)
class Action:
    name: str
    version: str
    tool: str
    pin: str
    raw: bytes
    schema: dict
    format_version: str = "1"


def load_catalog(registry, root):
    config = document(read(registry))
    fields(config, ("version", "entries"))
    entries = config["entries"]
    require(config["version"] == "1" and isinstance(entries, list) and 1 <= len(entries) <= 64)
    root = root.resolve(strict=True)
    catalog, tools, files = {}, set(), set()
    for entry in entries:
        fields(entry, ("action", "version", "file", "sha256"))
        name = identifier(entry["action"])
        require(matches(name, r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+"))
        version = identifier(entry["version"])
        filename = entry["file"]
        require(matches(filename, r"[A-Za-z0-9_-]{1,64}\.json") and not PureWindowsPath(filename).is_reserved())
        require(filename.lower() not in files and (name, version) not in catalog)
        path = (root / filename).resolve(strict=True)
        require(path.parent == root and path.is_file())
        raw = read(path)
        digest = sha256(raw).hexdigest()
        require(digest == entry["sha256"])
        doc = document(raw, numbers=True)
        keys = ("action", "version", "tool", "fields")
        format_version = doc.get("format_version", "1")
        require(format_version in ("1", "2"))
        fields(doc, (*keys, "format_version") if "format_version" in doc else keys)
        require((doc["action"], doc["version"]) == (name, version))
        tool = identifier(doc["tool"])
        require(tool not in tools)
        schema = doc["fields"]
        if format_version == "2":
            specs = typed_fields(schema, allow_empty=True)
        else:
            require(isinstance(schema, dict) and 1 <= len(schema) <= 32)
            specs = {identifier(k): Field.parse(v) for k, v in schema.items()}
        catalog[name, version] = Action(name, version, tool, digest, raw, specs, format_version)
        files.add(filename.lower())
        tools.add(tool)
    return catalog


def arguments(action, values):
    fields(values, action.schema)
    for key, spec in action.schema.items():
        spec.check(values[key])
    return values
