"""Interpret a complete call to the offline demo update_file tool."""

from dataclasses import dataclass

from .parser import parse_bytes
from .reviewer_trust import UPDATE, fields, require
from .structure import EXACT_TEXT_LIMIT, supported_exact_text

CALL_LIMIT = 65_536


@dataclass(frozen=True, slots=True)
class UpdateCall:
    action: str
    host: str
    provider_id: str
    branch: str
    base_revision: str
    path: str
    text: bytes


def parse_update_call(raw: bytes) -> UpdateCall:
    call = parse_bytes(raw, limit=CALL_LIMIT)
    fields(call, ("version", "tool", "arguments"))
    require(call["version"] == "1" and call["tool"] == "update_file")
    args = call["arguments"]
    fields(args, ("host", "provider_id", "branch", "base_revision", "path", "text"))
    require(all(isinstance(value, str) for value in args.values()))
    text = args["text"].encode("utf-8")
    require(len(text) <= EXACT_TEXT_LIMIT and supported_exact_text(args["text"]))
    return UpdateCall(UPDATE, args["host"], args["provider_id"], args["branch"],
                      args["base_revision"], args["path"], text)
