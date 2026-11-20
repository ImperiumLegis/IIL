"""Organization-selected public reviewer keys and exact repository grants."""

from base64 import b64decode, b64encode
from dataclasses import dataclass
from hashlib import sha256
import re

from nacl.bindings import crypto_core_ed25519_is_valid_point

from .parser import parse_bytes

TRUST_LIMIT = 65_536
UPDATE = "github.file.update"
_HOST = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"


def require(condition):
    if not condition:
        raise ValueError("Invalid receipt or trust record")


def fields(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names))


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value, re.ASCII) is not None


def identifier(value):
    require(matches(value, r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"))
    return value


def binary(value, size):
    require(isinstance(value, str) and value.isascii())
    raw = b64decode(value, validate=True)
    require(len(raw) == size and b64encode(raw).decode("ascii") == value)
    return raw


@dataclass(frozen=True)
class Reviewer:
    public_key: bytes
    grants: frozenset

    @property
    def fingerprint(self):
        return sha256(self.public_key).hexdigest()

    def allows(self, repository):
        return (repository["host"], repository["provider_id"], UPDATE) in self.grants


@dataclass(frozen=True)
class Trust:
    organization: str
    reviewers: dict

    def lookup(self, name):
        require(identifier(name) in self.reviewers)
        return self.reviewers[name]


def _grant(entry):
    fields(entry, ("host", "provider_id", "action"))
    host = entry["host"]
    require(matches(host, _HOST) and len(host) <= 253)
    require(matches(entry["provider_id"], r"[1-9][0-9]{0,19}"))
    require(entry["action"] == UPDATE)
    return host, entry["provider_id"], UPDATE


def load_trust(raw):
    doc = parse_bytes(raw, limit=TRUST_LIMIT)
    fields(doc, ("format_version", "organization", "reviewers"))
    organization = identifier(doc["organization"])
    require(doc["format_version"] == "1" and isinstance(doc["reviewers"], list))
    reviewers = {}
    keys = set()
    for entry in doc["reviewers"]:
        fields(entry, ("id", "public_key", "grants"))
        name = identifier(entry["id"])
        key = binary(entry["public_key"], 32)
        require(crypto_core_ed25519_is_valid_point(key))
        require(name not in reviewers and key not in keys)
        require(isinstance(entry["grants"], list))
        grants = frozenset(_grant(grant) for grant in entry["grants"])
        require(len(grants) == len(entry["grants"]))
        reviewers[name] = Reviewer(key, grants)
        keys.add(key)
    return Trust(organization, reviewers)
