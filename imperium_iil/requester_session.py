"""Operator-enrolled public identities of active requester processes."""

from dataclasses import dataclass
from hashlib import sha256

from nacl.bindings import crypto_core_ed25519_is_valid_point

from .parser import parse_bytes
from .reviewer_trust import TRUST_LIMIT, binary, fields, identifier, matches, require


@dataclass(frozen=True)
class Session:
    organization: str
    requester: str
    session: str
    public_key: bytes

    def claims(self):
        return {"requester": self.requester, "session": self.session,
                "session_key_fingerprint": sha256(self.public_key).hexdigest()}


def load_sessions(raw, organization):
    doc = parse_bytes(raw, limit=TRUST_LIMIT)
    fields(doc, ("version", "organization", "sessions"))
    require(doc["version"] == "1" and identifier(doc["organization"]) == organization)
    require(isinstance(doc["sessions"], list))
    sessions = {}
    keys = set()
    for item in doc["sessions"]:
        fields(item, ("requester", "session", "public_key"))
        sid = item["session"]
        require(matches(sid, r"[0-9a-f]{64}") and sid not in sessions)
        key = binary(item["public_key"], 32)
        require(crypto_core_ed25519_is_valid_point(key) and key not in keys)
        sessions[sid] = Session(organization, identifier(item["requester"]), sid, key)
        keys.add(key)
    return sessions
