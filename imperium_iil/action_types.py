"""Closed, bounded field descriptions for declarative manifest format 2."""

from dataclasses import dataclass
import re

from .reviewer_trust import fields, identifier, matches, require
from .structure import supported_exact_text


def bound(value, ceiling):
    require(matches(value, r"0|[1-9][0-9]{0,4}"))
    n = int(value)
    require(n <= ceiling)
    return n


def pattern(value):
    # A single wildcard consumes a nonempty identifier fragment. All other
    # characters are literals, including the dot in domain and file names.
    require(matches(value, r"[a-zA-Z0-9_@./:*-]{1,128}") and value.count("*") <= 1 and value != "*")
    parts = [re.escape(part) for part in value.split("*")]
    return re.compile(r"[A-Za-z0-9_-]+".join(parts), re.ASCII)


def numeric_range(kind, low, high):
    types = (int,) if kind == "integer" else (int, float)
    require(type(low) in types and type(high) in types and low <= high)
    return low, high


@dataclass(frozen=True)
class TypedField:
    kind: str
    bounds: tuple = ()
    pattern: re.Pattern | None = None
    choices: frozenset = frozenset()
    properties: dict | None = None
    item: "TypedField | None" = None

    @classmethod
    def parse(cls, spec):
        require(isinstance(spec, dict))
        kind = spec.get("type")
        if kind == "object":
            fields(spec, ("type", "fields"))
            return cls(kind, properties=typed_fields(spec["fields"]))
        if kind == "array":
            fields(spec, ("type", "least", "most", "items"))
            low, high = bound(spec["least"], 64), bound(spec["most"], 64)
            require(low <= high)
            return cls(kind, (low, high), item=cls.parse(spec["items"]))
        if kind == "string":
            keys = ("type", "min", "max")
            fields(spec, (*keys, "pattern") if "pattern" in spec else keys)
            low, high = bound(spec["min"], 16384), bound(spec["max"], 16384)
            require(low <= high)
            return cls(kind, (low, high), pattern(spec["pattern"]) if "pattern" in spec else None)
        if kind in ("number", "integer"):
            fields(spec, ("type", "min", "max"))
            return cls(kind, numeric_range(kind, spec["min"], spec["max"]))
        if kind == "enum":
            fields(spec, ("type", "values"))
            choices = spec["values"]
            require(isinstance(choices, list) and 1 <= len(choices) <= 64)
            require(all(isinstance(v, str) and len(v) <= 256 and supported_exact_text(v) for v in choices))
            require(len(set(choices)) == len(choices))
            return cls(kind, choices=frozenset(choices))
        require(kind == "boolean")
        fields(spec, ("type",))
        return cls(kind)

    def check(self, value):
        if self.kind == "object":
            fields(value, self.properties)
            for key, spec in self.properties.items():
                spec.check(value[key])
        elif self.kind == "array":
            require(isinstance(value, list) and self.bounds[0] <= len(value) <= self.bounds[1])
            for item in value:
                self.item.check(item)
        elif self.kind == "string":
            require(isinstance(value, str) and supported_exact_text(value))
            require(self.bounds[0] <= len(value) <= self.bounds[1])
            require(self.pattern is None or self.pattern.fullmatch(value))
        elif self.kind == "enum":
            require(isinstance(value, str) and value in self.choices)
        elif self.kind == "boolean":
            require(type(value) is bool)
        else:
            types = (int,) if self.kind == "integer" else (int, float)
            require(type(value) in types and self.bounds[0] <= value <= self.bounds[1])


def typed_fields(schema):
    require(isinstance(schema, dict) and 1 <= len(schema) <= 32)
    return {identifier(key): TypedField.parse(spec) for key, spec in schema.items()}
