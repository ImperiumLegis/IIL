"""Interpret a complete call to the offline demo update_file tool."""

from dataclasses import dataclass

from .parser import parse_bytes
from .reviewer_trust import UPDATE, fields, require
from .structure import UTF8_ENVELOPE_LIMIT, exact_text_error

CALL_LIMIT = UTF8_ENVELOPE_LIMIT


@dataclass(frozen=True, slots=True)
class UpdateCall:
    action: str
    host: str
    provider_id: str
    branch: str
    base_revision: str
    path: str
    text: bytes
    format_version: str = "1"


def parse_update_call(raw: bytes) -> UpdateCall:
    call = parse_bytes(raw, limit=CALL_LIMIT)
    fields(call, ("version", "tool", "arguments"))
    version = call["version"]
    require(version in ("1", "2") and call["tool"] == "update_file")
    require(version == "2" or len(raw) <= 65_536)
    args = call["arguments"]
    fields(args, ("host", "provider_id", "branch", "base_revision", "path", "text"))
    require(all(isinstance(value, str) for value in args.values()))
    require(exact_text_error(args["text"], "0.3" if version == "2" else "0.2") is None)
    text = args["text"].encode("utf-8")
    return UpdateCall(UPDATE, args["host"], args["provider_id"], args["branch"],
                      args["base_revision"], args["path"], text, version)
