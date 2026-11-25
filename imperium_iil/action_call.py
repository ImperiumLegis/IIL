"""Decode one tool-call object in an operator-selected wire format."""

from .action_manifest import document
from .reviewer_trust import fields, identifier, require

FORMATS = ("iil", "mcp", "openai-chat")


def decode_call(raw, call_format):
    obj = document(raw, numbers=True)
    if call_format == "iil":
        fields(obj, ("tool", "arguments"))
        return obj["tool"], obj["arguments"]
    if call_format == "mcp":
        fields(obj, ("jsonrpc", "id", "method", "params"))
        require(obj["jsonrpc"] == "2.0" and obj["method"] == "tools/call")
        if type(obj["id"]) is not int:
            identifier(obj["id"])
        params = obj["params"]
        require(isinstance(params, dict) and "name" in params and params.keys() <= {"name", "arguments", "_meta"})
        if "_meta" in params:
            meta = params["_meta"]
            require(isinstance(meta, dict) and meta.keys() <= {"progressToken"})
            if "progressToken" in meta:
                token = meta["progressToken"]
                require(type(token) in (int, float) or
                        (isinstance(token, str) and 1 <= len(token) <= 256 and token.isascii() and token.isprintable()))
        args = params.get("arguments", {})
        require(isinstance(args, dict))
        return params["name"], args
    require(call_format == "openai-chat")
    fields(obj, ("id", "type", "function"))
    identifier(obj["id"])
    require(obj["type"] == "function")
    function = obj["function"]
    fields(function, ("name", "arguments"))
    encoded = function["arguments"]
    require(isinstance(encoded, str))
    return function["name"], document(encoded.encode("utf-8"), numbers=True)
